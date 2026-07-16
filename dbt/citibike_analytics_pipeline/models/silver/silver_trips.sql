
-- merging schema discrepencies between legacy and current era

-- materialize as a table
{{ config(materialized='table') }}

with legacy as (

    select
        -- create a ride_id since legacy has no ride_id
        concat('legacy', bikeid, starttime) as ride_id,

        -- No rideable_type (electric/classic) distinction in legacy; create column as NULL
        cast(null as string) as rideable_type,

        -- Determined the different starttime formats
        coalesce(
            try_to_timestamp(starttime, 'yyyy-MM-dd HH:mm:ss.SSSS'),
            try_to_timestamp(starttime, 'yyyy-MM-dd HH:mm:ss'),
            try_to_timestamp(starttime, 'M/d/yyyy HH:mm:ss'),
            try_to_timestamp(starttime, 'M/d/yyyy H:mm')
        ) as started_at,

        -- Determined the different stoptime formats
        coalesce(
            try_to_timestamp(stoptime, 'yyyy-MM-dd HH:mm:ss.SSSS'),
            try_to_timestamp(stoptime, 'yyyy-MM-dd HH:mm:ss'),
            try_to_timestamp(stoptime, 'M/d/yyyy HH:mm:ss'),
            try_to_timestamp(stoptime, 'M/d/yyyy H:mm')
        ) as ended_at,
    
        try_cast(tripduration as bigint) as trip_duration_seconds,
        `start station id` as start_station_id,
        `start station name` as start_station_name,
        try_cast(`start station latitude` as double) as start_lat,
        try_cast(`start station longitude` as double) as start_lng,

        `end station id` as end_station_id,
        `end station name` as end_station_name,
        try_cast(`end station latitude` as double) as end_lat,
        try_cast(`end station longitude` as double) as end_lng,

        -- Converting the usertype in legacy era to what is in current_era
        case
            when usertype = 'Subscriber' then 'member'
            when usertype = 'Customer' then 'casual'
            else lower(usertype)
        end as rider_type,

        -- bikeid is an identifier, so no need to cast to int
        bikeid as bike_id,
        source_file,

        -- cast as a timestamp
        try_to_timestamp(ingestion_timestamp) as ingestion_timestamp,
        
        schema_era

    from {{ source('bronze', 'trips_raw_legacy') }}

),

current_era as (

    select
        ride_id,
        rideable_type,

        try_to_timestamp(started_at, 'yyyy-MM-dd HH:mm:ss.SSS') as started_at,
        try_to_timestamp(ended_at, 'yyyy-MM-dd HH:mm:ss.SSS') as ended_at,

        -- Create the trip duration that isn't present
        try_to_timestamp(ended_at)::long - try_to_timestamp(started_at)::long as trip_duration_seconds,
        
        start_station_id,
        start_station_name,
        try_cast(start_lat as double) as start_lat,
        try_cast(start_lng as double) as start_lng,

        end_station_id,
        end_station_name,
        try_cast(end_lat as double) as end_lat,
        try_cast(end_lng as double) as end_lng,

        member_casual as rider_type,

        -- no bike_id, create as NULL
        cast(null as string) as bike_id,

        source_file,

        -- cast as a timestamp
        try_to_timestamp(ingestion_timestamp) as ingestion_timestamp,

        schema_era

    from {{ source('bronze', 'trips_raw_current') }}

),

unioned as (

    select * from legacy
    union all
    select * from current_era

),

-- Important to check for any duplicates
-- Manually groups by ride_id and assigns row_number, later select only row = 1
deduped as (

    select
        *,
        row_number() over (
            partition by ride_id
            order by ingestion_timestamp desc
        ) as row_num

    from unioned

),

filtered as (

    select
        ride_id,
        rideable_type,
        started_at,
        ended_at,
        trip_duration_seconds,
        start_station_id,
        start_station_name,
        start_lat,
        start_lng,
        end_station_id,
        end_station_name,
        end_lat,
        end_lng,
        rider_type,
        bike_id,
        source_file,
        ingestion_timestamp,
        schema_era,

        -- Flag trips with a null start or end station ID
        -- These could be bikes that were lost, stolen, not returned.
        -- ~600k rows
        case
            when start_station_id is not null 
                and end_station_id is not null 
            then true
            else false
        end as is_complete_trip,

        -- for trips under 24 hours
        case
            when trip_duration_seconds > 86400
            then true
            else false
        end as is_over24hour_trip

    from deduped

    -- Removing any duplicates
    where row_num = 1
        -- duration must be positive
        and trip_duration_seconds > 0
        -- station IDs must be present
        and start_station_id is not null
        and end_station_id is not null

        -- Coordinates outside the NYC metro area are excluded. 
        -- Checked failing rows are legit coordinates that are way outside NYC
        and start_lat between 40.4 and 41.0
        and start_lng between -74.3 and -73.6
        and end_lat between 40.4 and 41.0
        and end_lng between -74.3 and -73.6

        -- Exclude a small number ~531 rows of current_era data that had started_at before 2020-01-01
        and not (schema_era = 'current' and started_at < '2020-01-01')

        -- ~202 rows, started_at time should be less than ended_at
        and started_at < ended_at

),

-- When running against the 'ci' target, only process
-- one month of source data to keep CI builds fast. This has no effect on
-- dev or prod targets, which process the full dataset.
ci_filter as (

    select *
    from filtered
    {% if target.name == 'ci' %}
    where source_file like '%202401%'
    {% endif %}

)

select * from ci_filter