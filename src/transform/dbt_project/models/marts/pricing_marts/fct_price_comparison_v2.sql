{#
    Model: fct_price_comparison_v2
    Layer: Gold - Pricing Marts (Fact Table)

    Description:
        Price comparison fact table with surrogate keys (Kimball-compliant).
        Shows price variations for products available in multiple stores.

    Grain: product_key + date_key + store_key (one row per product/store/day, only multi-store products)

    Business Logic:
        - Filter to products available in 2+ stores on same day
        - Calculate price ranking and spread metrics
        - Use surrogate keys for all dimension references

    Lineage: fct_daily_prices → dim_* → fct_price_comparison_v2
#}

{{
    config(
        materialized='table',
        tags=['pricing', 'fact', 'comparison']
    )
}}

with
    daily_prices as (
        select
            product_key
            , product_id
            , product_name
            , brand_key
            , brand
            , store_key
            , supermarket
            , region_key
            , region
            , date_key
            , scraped_date
            , min_price
            , avg_price
            , is_available
        from {{ ref('fct_daily_prices') }}
        where min_price is not null
    )

    , normalized_product_names as (
        {# Normalize product names for cross-store matching #}
        select
            *
            , lower(trim(regexp_replace(product_name, '\s+', ' ', 'g'))) as product_name_normalized
        from daily_prices
    )

    , products_multiple_stores as (
        {# Filter to products available in 2+ stores on same day (by normalized name) #}
        select
            product_name_normalized
            , date_key
        from normalized_product_names
        group by product_name_normalized, date_key
        having count(distinct store_key) >= 2
    )

    , price_comparison as (
        select
            p.product_key
            , p.product_id
            , p.product_name
            , p.product_name_normalized
            , p.brand_key
            , p.brand
            , p.date_key
            , p.scraped_date
            , p.store_key
            , p.supermarket
            , p.region_key
            , p.region
            , p.min_price
            , p.avg_price
            , p.is_available

            -- Window functions for price ranking (by normalized name across stores)
            , min(p.min_price) over (partition by p.product_name_normalized, p.date_key) as lowest_price
            , max(p.min_price) over (partition by p.product_name_normalized, p.date_key) as highest_price
            , avg(p.min_price) over (partition by p.product_name_normalized, p.date_key) as market_avg_price

            -- Ranking (by normalized name across stores)
            , row_number() over (partition by p.product_name_normalized, p.date_key order by p.min_price asc) as price_rank

        from normalized_product_names p
        inner join products_multiple_stores m
            on p.product_name_normalized = m.product_name_normalized
            and p.date_key = m.date_key
    )

    , final as (
        select
            product_key
            , product_id
            , product_name
            , brand_key
            , brand
            , date_key
            , scraped_date
            , store_key
            , supermarket
            , region_key
            , region
            , min_price
            , avg_price
            , is_available

            -- Price metrics
            , lowest_price
            , highest_price
            , market_avg_price
            , price_rank

            -- Calculated measures
            , (min_price - lowest_price) as price_diff_vs_lowest
            , round(((min_price - lowest_price) / nullif(lowest_price, 0)) * 100, 2) as price_premium_pct
            , (highest_price - lowest_price) as price_spread
            , round(((highest_price - lowest_price) / nullif(lowest_price, 0)) * 100, 2) as price_spread_pct

            -- Flags
            , case when price_rank = 1 then true else false end as is_cheapest
            , case when min_price = highest_price then true else false end as is_most_expensive

        from price_comparison
    )

select
    *
    , current_timestamp as loaded_at
from final
