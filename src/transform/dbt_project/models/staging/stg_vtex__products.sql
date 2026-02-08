{#
    Model: stg_vtex__products
    Layer: Staging (Ephemeral)

    Description:
        Unifies raw product data from 5 VTEX supermarkets (Bistek, Fort, Giassi, Carrefour, Angeloni).
        Applies basic cleansing and column standardization.

    Grain: product_id + region + run_id (raw, without deduplication)

    Notes:
        - Ephemeral (does not materialize table, only CTE for downstream models)
        - No contracts (staging layer)
        - Data still contains duplicates (dedup happens in trusted layer)
        - Uses Hive partitioning columns (supermarket, region) from bronze layer
        - Carrefour uses HTML scraping (API blocked), may have different data quality
#}

with
    bistek_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items  -- Keep nested for processing in trusted
            , supermarket  -- From Hive partitioning
            , region  -- From Hive partitioning
            , coalesce(_metadata_postal_code, NULL) as postal_code
            , coalesce(_metadata_hub_id, NULL) as hub_id
            , coalesce(_metadata_run_id, filename) as run_id
            , coalesce(cast(_metadata_scraped_at as timestamp), scraped_at, current_timestamp) as scraped_at
        from {{ source_parquet('bronze_bistek', 'products') }}
        where productId is not null  -- Basic quality filter
    )

    , fort_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , supermarket  -- From Hive partitioning
            , region  -- From Hive partitioning
            , coalesce(_metadata_postal_code, NULL) as postal_code
            , coalesce(_metadata_hub_id, NULL) as hub_id
            , coalesce(_metadata_run_id, filename) as run_id
            , coalesce(cast(_metadata_scraped_at as timestamp), scraped_at, current_timestamp) as scraped_at
        from {{ source_parquet('bronze_fort', 'products') }}
        where productId is not null
    )

    , giassi_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , supermarket  -- From Hive partitioning
            , region  -- From Hive partitioning
            , coalesce(_metadata_postal_code, NULL) as postal_code
            , coalesce(_metadata_hub_id, NULL) as hub_id
            , coalesce(_metadata_run_id, filename) as run_id
            , coalesce(cast(_metadata_scraped_at as timestamp), scraped_at, current_timestamp) as scraped_at
        from {{ source_parquet('bronze_giassi', 'products') }}
        where productId is not null
    )

    , carrefour_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , supermarket  -- From Hive partitioning
            , region  -- From Hive partitioning
            , coalesce(_metadata_postal_code, NULL) as postal_code
            , coalesce(_metadata_hub_id, NULL) as hub_id
            , coalesce(_metadata_run_id, filename) as run_id
            , coalesce(cast(_metadata_scraped_at as timestamp), scraped_at, current_timestamp) as scraped_at
        from {{ source_parquet('bronze_carrefour', 'products') }}
        where productId is not null
    )

    , angeloni_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , supermarket  -- From Hive partitioning
            , region  -- From Hive partitioning
            , coalesce(_metadata_postal_code, NULL) as postal_code
            , coalesce(_metadata_hub_id, NULL) as hub_id
            , coalesce(_metadata_run_id, filename) as run_id
            , coalesce(cast(_metadata_scraped_at as timestamp), scraped_at, current_timestamp) as scraped_at
        from {{ source_parquet('bronze_angeloni', 'products') }}
        where productId is not null
    )

    , unified as (
        select * from bistek_raw
        union all
        select * from fort_raw
        union all
        select * from giassi_raw
        union all
        select * from carrefour_raw
        union all
        select * from angeloni_raw
    )

select *
from unified
