{#
    Model: dim_region
    Layer: Gold - Conformed Dimensions

    Description:
        Region dimension with geographic and demographic attributes.
        One row per unique region code across all stores.

    Grain: region (one row per region code)

    Business Logic:
        - Extract distinct regions from trusted layer
        - Parse region code to city and neighborhood
        - Add geographic metadata (state, postal code)

    Lineage: tru_product → dim_region
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension']
    )
}}

with
    regions_base as (
        select distinct
            region as region_code
            , postal_code
            , supermarket
        from {{ ref('tru_product') }}
        where region is not null
    )

    , regions_parsed as (
        select
            region_code
            , postal_code

            -- Parse region code (format: city_neighborhood)
            , split_part(region_code, '_', 1) as city_code
            , split_part(region_code, '_', 2) as neighborhood_code

            -- City name mapping (manual for now, should be dimension later)
            , case split_part(region_code, '_', 1)
                when 'florianopolis' then 'Florianópolis'
                when 'criciuma' then 'Criciúma'
                when 'saojose' then 'São José'
                when 'torres' then 'Torres'
                when 'itajai' then 'Itajaí'
                when 'brusque' then 'Brusque'
                when 'palhoca' then 'Palhoça'
                when 'lages' then 'Lages'
                when 'blumenau' then 'Blumenau'
                when 'poa' then 'Porto Alegre'
                when 'joinville' then 'Joinville'
                when 'balneario' then 'Balneário Camboriú'
                else split_part(region_code, '_', 1)
            end as city_name

            -- State mapping (based on city)
            , case split_part(region_code, '_', 1)
                when 'poa' then 'RS'
                when 'torres' then 'RS'
                else 'SC'
            end as state_code

            , case split_part(region_code, '_', 1)
                when 'poa' then 'Rio Grande do Sul'
                when 'torres' then 'Rio Grande do Sul'
                else 'Santa Catarina'
            end as state_name

            -- Stores operating in this region
            , list(distinct supermarket order by supermarket) as stores_in_region
            , count(distinct supermarket) as store_count

        from regions_base
        group by region_code, postal_code
    )

    , regions_with_keys as (
        select
            -- Surrogate key
            row_number() over (order by region_code) as region_key

            -- Natural key
            , region_code

            -- Geographic attributes
            , city_code
            , city_name
            , neighborhood_code
            , state_code
            , state_name
            , postal_code

            -- Business attributes
            , stores_in_region
            , store_count

            -- Classification
            , case
                when city_name in ('Florianópolis', 'Porto Alegre', 'Joinville', 'Blumenau') then 'Capital/Major City'
                when store_count >= 2 then 'Multi-store Market'
                else 'Single-store Market'
            end as market_type

        from regions_parsed
    )

select
    *
    , current_timestamp as loaded_at
from regions_with_keys
