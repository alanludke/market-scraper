{#
    Model: dim_store_location
    Layer: Gold - Conformed Dimensions (Bridge Table)

    Description:
        Bridge table connecting stores to locations (many-to-many relationship).
        Each store can have multiple locations, and each location can have multiple stores.

    Grain: One row per unique store_key + location_key combination

    Business Logic:
        - Extract all store + region combinations from tru_product
        - Join with dim_store to get store_key
        - Join with dim_location to get location_key
        - Generate surrogate keys

    Lineage: tru_product → dim_store → dim_location → dim_store_location

    Usage:
        - Join fact tables to both store AND location dimensions
        - Enables queries like "show all stores in Florianópolis - Centro"
        - Coverage gap analysis "which stores are NOT in location X"
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension', 'bridge']
    )
}}

with
    store_region_combos as (
        -- Extract all unique store + region combinations
        select distinct
            supermarket as store_id
            , region as region_code
        from {{ ref('tru_product') }}
        where supermarket is not null
          and region is not null
    )

    , with_dimension_keys as (
        -- Join to get surrogate keys from dimension tables
        select
            sr.store_id
            , sr.region_code
            , s.store_key
            , l.location_key
            , l.city_name
            , l.neighborhood_name
        from store_region_combos sr
        inner join {{ ref('dim_store') }} s
            on sr.store_id = s.store_id
        inner join {{ ref('dim_location') }} l
            on sr.region_code = l.location_id
    )

    , with_surrogate_key as (
        select
            row_number() over (order by store_key, location_key) as store_location_key  -- Surrogate key

            -- Foreign keys
            , store_key
            , location_key

            -- Denormalized attributes for convenience (from dimensions)
            , store_id
            , region_code as location_id
            , city_name
            , neighborhood_name

            -- Operational attributes (placeholders for future enhancement)
            , null::varchar as store_address  -- Full address of store at this location
            , null::varchar as hub_id         -- VTEX hub_id (from stores.yaml)
            , null::varchar as sc_code        -- Sales channel code
            , true as is_active               -- Is store still operating at this location?
            , null::date as opened_at         -- Date store opened at this location
            , null::date as closed_at         -- Date store closed (if applicable)

            -- Metadata
            , current_timestamp as created_at
            , current_timestamp as updated_at

        from with_dimension_keys
    )

select * from with_surrogate_key
