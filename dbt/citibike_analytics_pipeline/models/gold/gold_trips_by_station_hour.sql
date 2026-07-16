
-- Trip volume by station, date, and hour of day 
-- Excludes incomplete trips (is_complete_trip = false) 
-- and trips over 24 hours (is_over24hour_trip = true), since both likely represent lost/
-- abandoned bikes

with base as (

    select
        start_station_id,
        start_station_name,
        date(started_at) as trip_date,
        hour(started_at) as trip_hour,
        rider_type,
        ride_id
    from {{ ref('silver_trips') }}
    where is_complete_trip = true
      and is_over24hour_trip = false
)

select
    start_station_id,
    start_station_name,
    trip_date,
    trip_hour,
    count(*) as trip_count,
    count(case when rider_type = 'member' then 1 end) as member_trip_count,
    count(case when rider_type = 'casual' then 1 end) as casual_trip_count

from base
group by
    start_station_id,
    start_station_name,
    trip_date,
    trip_hour