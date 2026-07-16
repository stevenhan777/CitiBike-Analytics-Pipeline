-- Fails if net_flow doesn't exactly equal departure_count - arrival_count
-- Catches logic errors in the join/aggregation.

select *
from {{ ref('gold_station_net_flow') }}
where net_flow != (departure_count - arrival_count)