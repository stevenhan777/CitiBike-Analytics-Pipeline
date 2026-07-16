-- Daily comparison of rider_type: member vs. casual rider behavior 
-- trip volume and average trip duration, split by rider type.

with base as (

    select
        date(started_at) as trip_date,
        rider_type,
        trip_duration_seconds,
        ride_id
    from {{ ref('silver_trips') }}
    where is_complete_trip = true
      and is_over24hour_trip = false
      and rider_type is not null
)

select
    trip_date,
    rider_type,
    count(*) as trip_count,
    avg(trip_duration_seconds) as avg_trip_duration_seconds,
    percentile_approx(trip_duration_seconds, 0.5) as median_trip_duration_seconds

from base
group by
    trip_date,
    rider_type