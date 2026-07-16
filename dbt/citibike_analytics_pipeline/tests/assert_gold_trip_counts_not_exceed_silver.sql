-- Fails if any gold model's total trip count exceeds the total number of
-- eligible (complete trips and not over 24 hours) trips in silver 

with silver_total as (
    select count(*) as cnt
    from {{ ref('silver_trips') }}
    where is_complete_trip = true and is_over24hour_trip = false
),

gold_total as (
    select sum(trip_count) as cnt
    from {{ ref('gold_trips_by_station_hour') }}
)

select *
from silver_total, gold_total
where gold_total.cnt > silver_total.cnt