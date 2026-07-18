# Citi Bike Analytics Pipeline

A data pipeline that ingests Citi Bike trip data from 2014 to 2026 from Citi Bike S3 bucket: https://citibikenyc.com/system-data.
The data is processed through a medallion architecture (bronze -> silver -> gold) on Databricks using dbt. Orchestration is done with Databricks Workflows and GitHub Actions CI/CD.

## Architecture

```
S3 bucket
    |
    v
Landing Volume on DataBricks
    |
    v
Bronze (Delta tables, two schema eras kept separate)
    |
    v
Silver (dbt: consolidated schema, typed features, and removed duplicates)
    |
    v
Gold (dbt: four business marts)
```

## Data Source

Citi Bike publishes monthly trip data on a public S3 Bucket: https://s3.amazonaws.com/tripdata/index.html. The folders have structural variations. 

- From 2014 to 2023: one zip file per year, containing month subfolders (some as plain folders, some within zip files), with pre-2020 months using "1_January" folder names and 2020+ months using "YYYYMM" names. 
- From 2024 to present: one zip file per month, containing the CSV directly.

I build a custom download/extraction pipeline (src/bronze/) that will load the data in a consistent folder structure to the landing Volume.

```
/Volumes/<catalog>/landing/raw/
    {year}-citibike-tripdata/
        {yyyymm}-citibike-tripdata/
            {yyyymm}-citibike-tripdata.csv
```

Multiple CSVs found within a single month are combined into 1 file, only keeping the header of the first file. Year folders that have stray CSVs not contained within a Month folder are ignored. 

## Bronze Layer

There was a schema change starting with 2020 January trips. For Bronze, I keep the two schemas separate.

- bronze.trips_raw_legacy: 
    - tripduration	
    - starttime	
    - stoptime	
    - start station id	
    - start station name	
    - start station latitude	
    - start station longitude	
    - end station id	
    - end station name	
    - end station latitude	
    - end station longitude	
    - bikeid	
    - usertype	
    - birth year	
    - gender

- bronze.trips_raw_current: 
    - ride_id	
    - rideable_type	
    - started_at	
    - ended_at	
    - start_station_name	
    - start_station_id	
    - end_station_name	
    - end_station_id	
    - start_lat	
    - start_lng	
    - end_lat	
    - end_lng	
    - member_casual

All columns are read as string, with no inferSchema. Typing of features will be conducted in Silver Layer.

Additionally, I added the following rows to each dataset:
    - source_file 
    - ingestion_timestamp 
    - schema_era

## Silver Layer

Combines both bronze tables into one unified schema, typed features and removed duplicates.

- Timestamp recognition: legacy era timestamps appear in several different formats across different years. A coalesce chain of try_to_timestamp calls handles all different variants, returning NULL on rows that don't match.

- Rider type normalization: legacy usertype feature containing Subscriber/Customer is mapped to the current era member_casual feature as member/casual.

- The ride_id column is not present for legacy era trips so I genereated a synthetic one from bikeid + starttime.

- Removed duplicates: I keep the most recently ingested row per ride_id (unique identifier), to remove duplicates and in case ingestion is ran multiple times.

- Data quality filters: Durations that are negative or logically impossible, such as started_at >= ended_at, and latitude and longitude coordinates outside a NYC area. Spot checked the outliers and confirmed some coordinates from Montreal and Los Angeles coordinates.

- Data quality flags: Instead of dropping rows, decide to add a flag for is_complete_trip: (false when start or end station ID is missing) to likely indicate a lost/unreturned bike. And for is_long_trip: true when duration exceeds 24 hours since that is Citi Bike's policy window. Both represent potential analyzable phenomena to be preserved for downstream analytics. 

## Gold Layer

Four business marts, all excluding incomplete trips and is_long_trip outliers by default:

- gold_trips_by_station_hour:  trip volume by station, date, and hour of day
- gold_member_vs_casual: daily comparison (volume, average/median duration) based off rider type.
- gold_popular_routes: most common station to station (A -> B and B -> A) routes
- gold_station_net_flow: difference between daily departures and arrivals per station. Positive means station losing bikes, negative means station accumulating bikes.

## Testing

- dbt tests: Tested not_null, unique, accepted_values, and accepted_range on key columns across silver and gold models. Also did singular tests assert_started_before_ended and consistency checks between models, such as total gold counts never exceed silver's row count.

- pytest unit tests (tests/unit/): cover the Python logic in the bronze download/extraction pipeline. Functions such as resolve_month_key(folder naming across both schema eras), and combine_csvs (combining multiplefiles while only keep header of first file).

## Orchestration

A Databricks Workflow runs three chained tasks:
1. download_data: download and extract source zip files from S3
2. ingest_bronze: (depends on Task 1) read CSVs into bronze Delta tables
3. dbt_transform: (depends on Task 2) Databricks dbt task running dbt deps, dbt run, and dbt test

Scheduled to run daily.

## CI/CD

- ci.yml (trigger on pull request): runs pytest against the bronze utility functions, then dbt build --target ci against an isolated citibike_ci catalog, which is filtered to a single month of data for speed. This doesn't affect the production tables.
- cd.yml (on branch merge to main): runs the full dbt build --target prod on the real citibike catalog, rebuilding all of silver and gold layers from the complete dataset.

This gives a development and production boundary. PRs are validated against a isolated catalog with a small data slice, and only a reviewed, merged change affects real production tables.

## Tech Stack

- Storage: Unity Catalog Volumes (landing), Delta Lake (bronze/silver/gold)
- Compute: Databricks Free Edition
- Transformation: dbt
- Testing: dbt tests, pytest
- Orchestration: Databricks Workflows
- CI/CD: GitHub Actions

## Limitations / Future Work

- A station dimension table to track station name/location changes over time
- Configure the Databricks Workflow as a Databricks Asset Bundle databricks.yml
- CI's dbt build is limited to one month of data for speed, and not a comprehensive validation of entire dataset.