-- Net bike flow per station per day, calulated as departures minus arrivals.
-- Full outer join necessary to track all rows
-- Positive net_flow = station loses more bikes than it gains
-- Negative net_flow = station gains more bikes than it loses
-- Around zero = roughly self balancing

with departures as (

    select
        start_station_id as station_id,
        start_station_name as station_name,
        date(started_at) as activity_date,
        count(*) as departure_count
    from {{ ref('silver_trips') }}
    where is_complete_trip = true
      and is_over24hour_trip = false
    group by
        start_station_id,
        start_station_name,
        date(started_at)
),

arrivals as (

    select
        end_station_id as station_id,
        end_station_name as station_name,
        date(ended_at) as activity_date,
        count(*) as arrival_count
    from {{ ref('silver_trips') }}
    where is_complete_trip = true
      and is_over24hour_trip = false
    group by
        end_station_id,
        end_station_name,
        date(ended_at)
),

combined as (

    select
        coalesce(d.station_id, a.station_id) as station_id,
        coalesce(d.station_name, a.station_name) as station_name,
        coalesce(d.activity_date, a.activity_date) as activity_date,
        coalesce(d.departure_count, 0) as departure_count,
        coalesce(a.arrival_count, 0) as arrival_count

    from departures d
    full outer join arrivals a
        on d.station_id = a.station_id
        and d.activity_date = a.activity_date
)

select
    station_id,
    station_name,
    activity_date,
    departure_count,
    arrival_count,
    departure_count - arrival_count as net_flow

from combined