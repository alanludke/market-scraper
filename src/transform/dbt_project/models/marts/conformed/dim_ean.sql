{#
    Model: dim_ean
    Layer: Gold - Conformed Dimensions

    Description:
        EAN dimension with OpenFoodFacts enrichment.
        One row per unique EAN from VTEX products.
        Enables product deduplication, price-per-kg analysis, and nutritional insights.

    Grain: ean_code (one row per EAN barcode)

    Business Logic:
        - Extract all unique EANs from VTEX products (tru_product)
        - LEFT JOIN with OpenFoodFacts enrichment
        - Fallback to 'Unknown' for missing OFF data (referential integrity maintained)
        - Classify nutrition quality based on Nutriscore grade
        - Track enrichment status for coverage monitoring

    Lineage: tru_product + stg_openfoodfacts__products → dim_ean
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension', 'ean']
    )
}}

with
    eans_from_vtex as (
        -- Extract all unique EANs from VTEX products
        select distinct
            unnest(eans) as ean_code
        from {{ ref('tru_product') }}
        where eans is not null
            and len(eans) > 0
    )

    , openfoodfacts_enrichment as (
        -- OpenFoodFacts data (deduplicated - keep one row per EAN)
        -- When multiple records exist for same EAN, pick the most recent one
        select
            ean_code
            , product_name
            , brands
            , categories
            , quantity as net_weight
            , countries as country_of_origin
            , nutriscore_grade
        from {{ ref('stg_openfoodfacts__products') }}
        qualify row_number() over (
            partition by ean_code
            order by scraped_at desc  -- Most recent scrape
        ) = 1
    )

    , ean_master as (
        -- LEFT JOIN to preserve all VTEX EANs (even if not in OpenFoodFacts)
        select
            v.ean_code

            -- Enriched attributes (with 'Unknown' fallback)
            , coalesce(o.product_name, 'Unknown') as canonical_name
            , coalesce(o.brands, 'Unknown') as canonical_brand
            , o.categories
            , o.net_weight
            , o.country_of_origin
            , o.nutriscore_grade

            -- Nutrition quality classification
            , case
                when o.nutriscore_grade in ('a', 'b') then 'Excellent'
                when o.nutriscore_grade = 'c' then 'Good'
                when o.nutriscore_grade = 'd' then 'Fair'
                when o.nutriscore_grade = 'e' then 'Poor'
                else 'Unknown'
              end as nutrition_quality

            -- Enrichment flag for coverage tracking
            , case when o.ean_code is not null then true else false end as is_enriched

        from eans_from_vtex v
        left join openfoodfacts_enrichment o
            on v.ean_code = o.ean_code
    )

    , with_surrogate_key as (
        -- Generate surrogate key (sequential)
        select
            row_number() over (order by ean_code) as ean_key
            , ean_code
            , canonical_name
            , canonical_brand
            , categories
            , net_weight
            , country_of_origin
            , nutriscore_grade
            , nutrition_quality
            , is_enriched
        from ean_master
    )

select
    *
    , current_timestamp as loaded_at
from with_surrogate_key
