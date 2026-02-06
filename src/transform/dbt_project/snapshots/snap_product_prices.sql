{% snapshot snap_product_prices %}

{#
    Snapshot: snap_product_prices
    Type: SCD Type 2 (Slowly Changing Dimension)

    Description:
        Tracks price history for products over time.
        Captures when prices change (both increases and decreases).

    Strategy: Timestamp
    Updated Field: scraped_at

    Business Use Cases:
        - Price evolution analysis ("what was price 30 days ago?")
        - Price change frequency
        - Promotional period identification
        - Price elasticity modeling

    Grain: product_id + supermarket + region + dbt_valid_from (one row per price change)
#}

{{
    config(
        target_schema='snapshots',
        unique_key='product_id || supermarket || region',
        strategy='timestamp',
        updated_at='scraped_at'
    )
}}

select
    product_id
    , product_name
    , brand
    , supermarket
    , region
    , min_price
    , avg_price
    , max_price
    , min_list_price
    , is_available
    , sku_count
    , total_available_quantity
    , scraped_date
    , scraped_at
from {{ ref('tru_product') }}

{% endsnapshot %}