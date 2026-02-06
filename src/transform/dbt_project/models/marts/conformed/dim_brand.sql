{#
    Model: dim_brand
    Layer: Gold - Conformed Dimensions

    Description:
        Brand dimension with attributes for brand analysis.
        One row per unique brand across all products.

    Grain: brand (one row per brand name)

    Business Logic:
        - Extract distinct brands from products
        - Count products per brand
        - Classify brand importance

    Lineage: tru_product → dim_brand
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension']
    )
}}

with
    brands_base as (
        select
            brand
            , count(distinct product_id) as product_count
            , count(distinct supermarket) as store_count
            , min(scraped_date) as first_seen_date
            , max(scraped_date) as last_seen_date
        from {{ ref('tru_product') }}
        where brand is not null
        group by brand
    )

    , brands_with_keys as (
        select
            -- Surrogate key
            row_number() over (order by product_count desc, brand) as brand_key

            -- Natural key
            , brand as brand_name

            -- Metrics
            , product_count
            , store_count

            -- Classification
            , case
                when product_count >= 100 then 'Major Brand'
                when product_count >= 20 then 'Medium Brand'
                when product_count >= 5 then 'Small Brand'
                else 'Niche Brand'
            end as brand_tier

            , case
                when store_count = 3 then 'All Stores'
                when store_count = 2 then 'Multi-store'
                else 'Single Store'
            end as distribution_level

            -- Dates
            , first_seen_date
            , last_seen_date

        from brands_base
    )

select
    *
    , current_timestamp as loaded_at
from brands_with_keys
