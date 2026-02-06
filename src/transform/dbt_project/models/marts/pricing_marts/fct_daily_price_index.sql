{#
    Model: fct_daily_price_index
    Layer: Gold - Pricing Marts

    Description:
        Daily aggregated price index metrics by store and region.
        Tracks overall price trends, inflation, and basket costs.

    Grain: supermarket + region + scraped_date

    Business Logic:
        - Average basket price per store/region
        - Product count and availability rates
        - Price distribution (min, max, median, percentiles)

    Lineage: tru_product → fct_daily_price_index
#}

{{
    config(
        materialized='table'
    )
}}

with
    daily_products as (
        select
            supermarket
            , region
            , scraped_date
            , product_id
            , product_name
            , min_price
            , avg_price
            , is_available
            , total_available_quantity
        from {{ ref('tru_product') }}
        where min_price is not null
    )

    , daily_aggregated as (
        select
            supermarket
            , region
            , scraped_date

            -- Product counts
            , count(distinct product_id) as total_products
            , count(distinct case when is_available then product_id end) as available_products
            , count(distinct case when not is_available then product_id end) as unavailable_products

            -- Price statistics
            , min(min_price) as min_product_price
            , max(min_price) as max_product_price
            , avg(min_price) as avg_product_price
            , median(min_price) as median_product_price
            , stddev(min_price) as stddev_product_price

            -- Percentiles
            , approx_quantile(min_price, 0.25) as p25_product_price
            , approx_quantile(min_price, 0.75) as p75_product_price
            , approx_quantile(min_price, 0.90) as p90_product_price
            , approx_quantile(min_price, 0.95) as p95_product_price

            -- Availability metrics
            , round(count(distinct case when is_available then product_id end)::numeric
                    / count(distinct product_id) * 100, 2) as availability_rate_pct

            -- Inventory
            , sum(total_available_quantity) as total_inventory_units

        from daily_products
        group by supermarket, region, scraped_date
    )

select
    *
    , current_timestamp as loaded_at
from daily_aggregated
