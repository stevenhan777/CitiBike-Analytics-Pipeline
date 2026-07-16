-- Most popular routes, aggregated across the full
-- dataset. A "route" is defined as a specific start station and end station
-- pair, regardless of direction (A->B and B->A are tracked separately)

with base as (

    select
        start_station_id,
        start_station_name,
        end_station_id,
        end_station_name,
        trip_duration_seconds,
        ride_id
    from {{ ref('silver_trips') }}
    where is_complete_trip = true
      and is_over24hour_trip = false
)

select
    start_station_id,
    start_station_name,
    end_station_id,
    end_station_name,
    count(*) as trip_count,
    avg(trip_duration_seconds) as avg_trip_duration_seconds

from base
group by
    start_station_id,
    start_station_name,
    end_station_id,
    end_station_name

order by trip_count desc