{#
    Model: fct_active_promotions
    Layer: Gold - Pricing Marts (Fact Table)

    Description:
        Active promotions fact table tracking discounts and promotional campaigns.
        Enables promotion effectiveness analysis and discount optimization.

    Grain: product_key + store_key + region_key + date_key (only products with promotions)

    Business Logic:
        - Filter to products with active promotions (discount > 0)
        - Calculate promotion metrics (discount %, savings)
        - Track promotional periods

    Lineage: fct_daily_prices → fct_active_promotions
#}

{{
    config(
        materialized='table',
        tags=['pricing', 'fact', 'promotions']
    )
}}

with
    products_with_promotions as (
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
            , min_list_price
            , discount_pct
            , avg_price
            , is_available

        from {{ ref('fct_daily_prices') }}
        where
            discount_pct > 0  -- Has active promotion
            and min_list_price > 0  -- Valid list price
            and min_price > 0  -- Valid current price
    )

    , promotion_metrics as (
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
            , min_price as promotional_price
            , min_list_price as regular_price
            , discount_pct as discount_percentage
            , avg_price

            -- Calculated measures
            , (min_list_price - min_price) as absolute_discount
            , round(discount_pct, 0) as discount_tier  -- Rounded to nearest integer for grouping

            -- Promotion classification
            , case
                when discount_pct >= 50 then 'Hot Deal (50%+)'
                when discount_pct >= 30 then 'Strong Discount (30-50%)'
                when discount_pct >= 15 then 'Moderate Discount (15-30%)'
                when discount_pct >= 5 then 'Light Discount (5-15%)'
                else 'Minimal Discount (<5%)'
            end as promotion_type

            , case
                when discount_pct >= 30 then true
                else false
            end as is_hot_deal

            , is_available

        from products_with_promotions
    )

select
    *
    , current_timestamp as loaded_at
from promotion_metrics
