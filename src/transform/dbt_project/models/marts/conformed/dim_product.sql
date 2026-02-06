{#
    Model: dim_product
    Layer: Gold - Conformed Dimensions

    Description:
        Product dimension with slowly changing attributes.
        Aggregates product information across all stores to create a unified catalog.

    Grain: product_id (conformed across stores)

    Business Logic:
        - Consolidates products that appear in multiple stores
        - Tracks which stores carry each product
        - Identifies the most common product name/brand across stores
        - Assigns surrogate key for fact table joins

    Lineage: tru_product → dim_product
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension']
    )
}}

with
    products_base as (
        select
            product_id
            , product_name
            , brand
            , product_url
            , supermarket
            , region
        from {{ ref('tru_product') }}
    )

    , product_aggregated as (
        select
            product_id

            -- Most common name/brand across stores (mode)
            , mode() within group (order by product_name) as product_name
            , mode() within group (order by brand) as brand

            -- Stores carrying this product
            , list(distinct supermarket order by supermarket) as stores_carrying
            , count(distinct supermarket) as store_count

            -- Total regions where available
            , count(distinct region) as region_count

            -- Sample URL (first alphabetically)
            , min(product_url) as sample_url

        from products_base
        group by product_id
    )

    , with_surrogate_key as (
        select
            -- Surrogate key (sequential integer)
            row_number() over (order by product_id) as product_key

            -- Natural key
            , product_id

            -- Attributes
            , product_name
            , brand
            , stores_carrying
            , store_count
            , region_count
            , sample_url

        from product_aggregated
    )

select
    *
    , current_timestamp as loaded_at
from with_surrogate_key
