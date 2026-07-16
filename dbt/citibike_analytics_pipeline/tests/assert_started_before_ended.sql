-- Fails if any trip's started_at is not before its ended_at.
select *
from {{ ref('silver_trips') }}
where started_at >= ended_at