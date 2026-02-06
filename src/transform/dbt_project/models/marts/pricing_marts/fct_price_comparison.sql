{#
    Model: fct_price_comparison
    Layer: Gold - Pricing Marts

    Description:
        Price comparison across stores for products available in multiple locations.
        Enables competitiveness analysis and price benchmarking.

    Grain: product_id + scraped_date

    Business Logic:
        - Shows price variations for same product across stores
        - Identifies cheapest/most expensive store for each product
        - Calculates price spread and relative savings

    Lineage: tru_product → fct_price_comparison
#}

{{
    config(
        materialized='table'
    )
}}

with
    daily_prices as (
        select
            product_id
            , product_name
            , brand
            , supermarket
            , min_price
            , avg_price
            , is_available
            , scraped_date
        from {{ ref('tru_product') }}
        where min_price is not null
    )

    , products_multiple_stores as (
        {# Filter to products available in 2+ stores on same day #}
        select
            product_id
            , scraped_date
        from daily_prices
        group by product_id, scraped_date
        having count(distinct supermarket) >= 2
    )

    , price_comparison as (
        select
            p.product_id
            , p.product_name
            , p.brand
            , p.scraped_date
            , p.supermarket
            , p.min_price
            , p.avg_price
            , p.is_available

            -- Window functions for price ranking
            , min(p.min_price) over (partition by p.product_id, p.scraped_date) as lowest_price
            , max(p.min_price) over (partition by p.product_id, p.scraped_date) as highest_price
            , avg(p.min_price) over (partition by p.product_id, p.scraped_date) as market_avg_price

            -- Ranking
            , row_number() over (partition by p.product_id, p.scraped_date order by p.min_price asc) as price_rank

        from daily_prices p
        inner join products_multiple_stores m
            on p.product_id = m.product_id
            and p.scraped_date = m.scraped_date
    )

    , final as (
        select
            product_id
            , product_name
            , brand
            , scraped_date
            , supermarket
            , min_price
            , avg_price
            , is_available

            -- Price metrics
            , lowest_price
            , highest_price
            , market_avg_price
            , price_rank

            -- Calculated fields
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
