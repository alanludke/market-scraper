{#
    Model: fct_promotion_summary
    Layer: Gold - Pricing Marts (Aggregate Fact)

    Description:
        Aggregated promotion metrics by store/region/date.
        Tracks promotion intensity, average discounts, and promotional product count.

    Grain: store_key + region_key + date_key

    Business Logic:
        - Count products on promotion per store/region
        - Calculate average discount percentage
        - Identify top promotional categories

    Lineage: fct_active_promotions → fct_promotion_summary
#}

{{
    config(
        materialized='table',
        tags=['pricing', 'fact', 'promotions', 'summary']
    )
}}

with
    promotion_aggregates as (
        select
            store_key
            , supermarket
            , region_key
            , region
            , date_key
            , scraped_date

            -- Promotion counts
            , count(distinct product_key) as products_on_promotion
            , count(distinct case when is_hot_deal then product_key end) as hot_deal_products
            , count(distinct brand_key) as brands_on_promotion

            -- Discount metrics
            , avg(discount_percentage) as avg_discount_pct
            , min(discount_percentage) as min_discount_pct
            , max(discount_percentage) as max_discount_pct
            , median(discount_percentage) as median_discount_pct

            -- Savings metrics
            , sum(absolute_discount) as total_potential_savings
            , avg(absolute_discount) as avg_absolute_discount

            -- Price distribution
            , avg(promotional_price) as avg_promotional_price
            , avg(regular_price) as avg_regular_price

        from {{ ref('fct_active_promotions') }}
        group by
            store_key
            , supermarket
            , region_key
            , region
            , date_key
            , scraped_date
    )

    , with_ratios as (
        select
            pa.*

            -- Join with total product count from fct_daily_prices
            , dp.total_products
            , round((pa.products_on_promotion::numeric / nullif(dp.total_products, 0)) * 100, 2) as promotion_penetration_pct

        from promotion_aggregates pa
        left join (
            select
                store_key
                , region_key
                , date_key
                , count(distinct product_key) as total_products
            from {{ ref('fct_daily_prices') }}
            group by store_key, region_key, date_key
        ) dp
            on pa.store_key = dp.store_key
            and pa.region_key = dp.region_key
            and pa.date_key = dp.date_key
    )

select
    *
    , current_timestamp as loaded_at
from with_ratios
