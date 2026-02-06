{#
    Model: stg_vtex__products
    Layer: Staging (Ephemeral)

    Description:
        Unifies raw product data from 4 VTEX supermarkets (Bistek, Fort, Giassi, Carrefour).
        Applies basic cleansing and column standardization.

    Grain: product_id + region + run_id (raw, without deduplication)

    Notes:
        - Ephemeral (does not materialize table, only CTE for downstream models)
        - No contracts (staging layer)
        - Data still contains duplicates (dedup happens in trusted layer)
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
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
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
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
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
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
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
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
        from {{ source_parquet('bronze_carrefour', 'products') }}
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
    )

select *
from unified
