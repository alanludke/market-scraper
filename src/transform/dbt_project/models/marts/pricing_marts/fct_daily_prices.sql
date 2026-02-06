{#
    Model: fct_daily_prices
    Layer: Gold - Pricing Marts (Fact Table)

    Description:
        Daily price snapshot fact table with surrogate keys.
        Main fact table for price analysis following Kimball methodology.

    Grain: product_key + store_key + region_key + date_key (one row per product/store/region/day)

    Business Logic:
        - Surrogate keys to all dimensions (dim_product, dim_store, dim_region, dim_date, dim_brand)
        - Price metrics (min, max, avg across SKUs)
        - Availability and inventory metrics
        - Designed for star schema queries

    Lineage: tru_product → dim_* → fct_daily_prices
#}

{{
    config(
        materialized='table',
        tags=['pricing', 'fact']
    )
}}

with
    base_products as (
        select
            product_id
            , product_name
            , brand
            , supermarket
            , region
            , scraped_date
            , min_price
            , max_price
            , avg_price
            , min_list_price
            , sku_count
            , is_available
            , total_available_quantity
            , run_id
            , scraped_at
            , eans  -- EANs array for dim_ean join
        from {{ ref('tru_product') }}
    )

    , with_dimension_keys as (
        select
            p.scraped_date

            -- Surrogate keys (FKs to dimensions)
            , dp.product_key
            , ds.store_key
            , dr.region_key
            , dd.date_key
            , db.brand_key
            , de.ean_key

            -- Degenerate dimensions (kept for convenience, but not FKs)
            , p.product_id
            , p.product_name
            , p.supermarket
            , p.region
            , p.brand

            -- Price measures
            , p.min_price
            , p.max_price
            , p.avg_price
            , p.min_list_price

            -- Calculated measures
            , p.max_price - p.min_price as price_range
            , case
                when p.min_list_price > 0 and p.min_price > 0
                    then round(((p.min_list_price - p.min_price) / p.min_list_price) * 100, 2)
                else 0
            end as discount_pct

            -- Inventory measures
            , p.sku_count
            , p.is_available
            , p.total_available_quantity

            -- Audit
            , p.run_id
            , p.scraped_at

        from base_products p

        -- Join to dimensions (surrogate keys)
        inner join {{ ref('dim_product') }} dp
            on p.product_id = dp.product_id

        inner join {{ ref('dim_store') }} ds
            on p.supermarket = ds.store_id

        inner join {{ ref('dim_region') }} dr
            on p.region = dr.region_code

        inner join {{ ref('dim_date') }} dd
            on p.scraped_date = dd.date_day

        left join {{ ref('dim_brand') }} db
            on p.brand = db.brand_name

        -- Join to dim_ean (LEFT JOIN - some products may have no EANs)
        left join {{ ref('dim_ean') }} de
            on de.ean_code = p.eans[1]  -- Use first EAN (most products have 1 EAN)
    )

select
    *
    , current_timestamp as loaded_at
from with_dimension_keys
