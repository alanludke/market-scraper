{#
    Model: fct_product_availability
    Layer: Gold - Inventory Marts

    Description:
        Product availability tracking across stores and regions.
        Identifies stockouts, low inventory, and supply chain issues.

    Grain: product_id + supermarket + region + scraped_date

    Business Logic:
        - Track availability status changes
        - Identify products out of stock
        - Flag low inventory situations

    Lineage: tru_product → fct_product_availability
#}

{{
    config(
        materialized='table'
    )
}}

with
    product_inventory as (
        select
            product_id
            , product_name
            , brand
            , supermarket
            , region
            , scraped_date
            , is_available
            , total_available_quantity
            , sku_count
            , min_price

        from {{ ref('tru_product') }}
    )

    , availability_metrics as (
        select
            product_id
            , product_name
            , brand
            , supermarket
            , region
            , scraped_date
            , is_available
            , total_available_quantity
            , sku_count
            , min_price

            -- Flags
            , case
                when not is_available then 'out_of_stock'
                when total_available_quantity = 0 then 'out_of_stock'
                when total_available_quantity <= 5 then 'low_stock'
                when total_available_quantity <= 20 then 'medium_stock'
                else 'in_stock'
            end as stock_status

            , case
                when total_available_quantity > 0 and total_available_quantity <= 5 then true
                else false
            end as is_low_inventory

        from product_inventory
    )

select
    *
    , current_timestamp as loaded_at
from availability_metrics
