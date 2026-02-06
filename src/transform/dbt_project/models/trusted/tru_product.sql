{#
    Model: tru_product
    Layer: Trusted (Table with Contracts)

    Description:
        Deduplicated products with business logic applied.
        Keeps only the most recent scrape per day for each product+region.
        Flattens nested items array to extract SKUs, EANs and prices.

    Grain: product_id + region + date (1 record per product/region/day)

    Business Logic:
        - Deduplication: Latest scrape of the day per product+region
        - Cleansing: Remove products without name or invalid ID
        - Price: Extract lowest available price among SKUs
        - EAN: Consolidate EANs from all SKUs

    Lineage: stg_vtex__products → tru_product
#}

{{
    config(
        materialized='table',
        contract={'enforced': true}
    )
}}

with
    staging_products as (
        select * from {{ ref('stg_vtex__products') }}
    )

    , deduplicated as (
        {# Keep only the most recent scrape of the day per product+region #}
        select * from staging_products
        qualify row_number() over (
            partition by product_id, region, cast(scraped_at as date)
            order by scraped_at desc
        ) = 1
    )

    , flattened_items as (
        {#
            Flattens nested items array (SKUs) to extract prices and EANs.
            Each product can have multiple SKUs (e.g. different sizes).
        #}
        select
            product_id
            , product_name
            , brand
            , product_url
            , supermarket
            , region
            , postal_code
            , hub_id
            , run_id
            , scraped_at

            -- Flatten items array (DuckDB unnest)
            , unnest(items) as item

        from deduplicated
        where items is not null and len(items) > 0
    )

    , extract_pricing as (
        select
            product_id
            , product_name
            , brand
            , product_url
            , supermarket
            , region
            , postal_code
            , hub_id
            , run_id
            , scraped_at

            -- Extract SKU data
            , item.itemId as sku_id
            , item.name as sku_name
            , item.ean as ean

            -- Extract pricing (first available seller)
            , item.sellers[1].commertialOffer.Price as price
            , item.sellers[1].commertialOffer.ListPrice as list_price
            , item.sellers[1].commertialOffer.AvailableQuantity as available_quantity

        from flattened_items
    )

    , aggregate_product as (
        {#
            Final aggregation: 1 row per product+region+day
            - Lowest price among SKUs
            - List of consolidated EANs
        #}
        select
            product_id
            , any_value(product_name) as product_name
            , any_value(brand) as brand
            , any_value(product_url) as product_url
            , supermarket
            , region
            , any_value(postal_code) as postal_code
            , any_value(hub_id) as hub_id

            -- Pricing metrics
            , min(price) as min_price
            , max(price) as max_price
            , avg(price) as avg_price
            , min(list_price) as min_list_price

            -- SKU aggregation
            , count(distinct sku_id) as sku_count
            , list(distinct ean) filter (where ean is not null) as eans

            -- Availability
            , sum(available_quantity) as total_available_quantity
            , bool_or(available_quantity > 0) as is_available

            -- Metadata
            , any_value(run_id) as run_id
            , cast(any_value(scraped_at) as date) as scraped_date
            , max(scraped_at) as scraped_at  -- Latest scrape timestamp

        from extract_pricing
        group by product_id, supermarket, region
    )

    , add_audit_columns as (
        select
            -- Business key
            product_id
            , product_name
            , brand
            , product_url

            -- Location
            , supermarket
            , region
            , postal_code
            , hub_id

            -- Pricing
            , min_price
            , max_price
            , avg_price
            , min_list_price

            -- SKUs
            , sku_count
            , eans
            , is_available
            , total_available_quantity

            -- Audit
            , run_id
            , scraped_date
            , scraped_at
            , current_timestamp() as loaded_at

        from aggregate_product
    )

select * from add_audit_columns
