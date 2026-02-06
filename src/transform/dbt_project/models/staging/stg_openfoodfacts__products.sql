{#
    Model: stg_openfoodfacts__products
    Layer: Staging (Ephemeral)

    Description:
        Staging model for OpenFoodFacts product data.
        Cleans and standardizes EAN data from bronze layer.

    Grain: code (one row per EAN barcode)

    Business Logic:
        - Rename 'code' → 'ean_code' for consistency
        - Trim product_name and brands
        - Lowercase nutriscore_grade (a-e)
        - Filter for valid EAN lengths (8, 13, 14)

    Lineage: bronze_openfoodfacts.products → stg_openfoodfacts__products
#}

{{
    config(
        materialized='ephemeral',
        tags=['staging', 'openfoodfacts', 'enrichment']
    )
}}

select
    -- Natural key
    code as ean_code

    -- Product attributes
    , trim(product_name) as product_name
    , trim(brands) as brands
    , categories
    , quantity
    , countries

    -- Nutritional score
    , lower(nutriscore_grade) as nutriscore_grade

    -- Additional attributes
    , ingredients_text
    , allergens
    , labels
    , packaging
    , image_url

    -- Metadata
    , _metadata_run_id as run_id
    , cast(_metadata_scraped_at as timestamp) as scraped_at

from {{ source_parquet('bronze_openfoodfacts', 'products') }}

where code is not null
    and length(code) in (8, 13, 14)  -- Valid EAN lengths
