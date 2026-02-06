{#
    Model: dim_location
    Layer: Gold - Conformed Dimensions

    Description:
        Location dimension with unique geographic locations (city + neighborhood).
        Consolidates locations across all stores for cross-store analysis.

    Grain: One row per unique location (city_name + neighborhood_code)

    Business Logic:
        - Extract unique locations from region_code in tru_product
        - Parse city and neighborhood from region_code (format: city_neighborhood)
        - Generate surrogate keys
        - Future: Add geocoding (lat/long) via API

    Lineage: tru_product → dim_location

    Usage:
        - Cross-store price comparison in same neighborhood
        - Geospatial analysis (heatmaps)
        - Coverage gap analysis (which stores are not in which locations)
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension', 'location']
    )
}}

with
    unique_regions as (
        -- Extract unique region codes from all products
        select distinct
            region as region_code
        from {{ ref('tru_product') }}
        where region is not null
    )

    , parsed_locations as (
        -- Parse region_code into city and neighborhood components
        select
            region_code as location_id

            -- Extract city (part before first underscore)
            , case
                when position('_' in region_code) > 0
                then left(region_code, position('_' in region_code) - 1)
                else region_code
            end as city_code

            -- Extract neighborhood (part after first underscore)
            , case
                when position('_' in region_code) > 0
                then substring(region_code, position('_' in region_code) + 1)
                else 'centro'  -- Default neighborhood if no underscore
            end as neighborhood_code

        from unique_regions
    )

    , with_city_names as (
        -- Map city codes to full city names (manual mapping for now)
        select
            location_id
            , city_code
            , neighborhood_code

            -- City name mapping (comprehensive list for SC/RS)
            , case city_code
                -- Santa Catarina - Greater Florianópolis
                when 'florianopolis' then 'Florianópolis'
                when 'saojose' then 'São José'
                when 'palhoca' then 'Palhoça'
                when 'biguacu' then 'Biguaçu'
                when 'sao_jose' then 'São José'

                -- Santa Catarina - North Coast
                when 'joinville' then 'Joinville'
                when 'jaragua' then 'Jaraguá do Sul'
                when 'araquari' then 'Araquari'

                -- Santa Catarina - Itajaí Valley
                when 'blumenau' then 'Blumenau'
                when 'itajai' then 'Itajaí'
                when 'balneario_camboriu' then 'Balneário Camboriú'
                when 'navegantes' then 'Navegantes'
                when 'brusque' then 'Brusque'
                when 'gaspar' then 'Gaspar'
                when 'porto_belo' then 'Porto Belo'

                -- Santa Catarina - South
                when 'tubarao' then 'Tubarão'
                when 'criciuma' then 'Criciúma'
                when 'ararangua' then 'Araranguá'
                when 'icara' then 'Içara'
                when 'laguna' then 'Laguna'
                when 'imbituba' then 'Imbituba'
                when 'morro_da_fumaca' then 'Morro da Fumaça'
                when 'sombrio' then 'Sombrio'

                -- Santa Catarina - West
                when 'chapeco' then 'Chapecó'
                when 'xanxere' then 'Xanxerê'
                when 'concordia' then 'Concórdia'
                when 'sao_miguel_do_oeste' then 'São Miguel do Oeste'

                -- Santa Catarina - Highlands
                when 'lages' then 'Lages'
                when 'sao_joaquim' then 'São Joaquim'
                when 'campos_novos' then 'Campos Novos'

                -- Rio Grande do Sul
                when 'poa' then 'Porto Alegre'
                when 'canoas' then 'Canoas'
                when 'torres' then 'Torres'
                when 'tramandai' then 'Tramandaí'
                when 'capao_da_canoa' then 'Capão da Canoa'

                -- Default: Title case the city code
                else upper(replace(city_code, '_', ' '))
            end as city_name

            -- Neighborhood name mapping (sample - expand as needed)
            , case neighborhood_code
                -- Florianópolis neighborhoods
                when 'costeira' then 'Costeira do Pirajubaé'
                when 'santa_monica' then 'Santa Mônica'
                when 'sacogrande' then 'Saco Grande'
                when 'centro' then 'Centro'
                when 'trindade' then 'Trindade'
                when 'campeche' then 'Campeche'
                when 'lagoa' then 'Lagoa da Conceição'

                -- São José neighborhoods
                when 'belavista' then 'Bela Vista'
                when 'areias' then 'Areias'
                when 'kobrasol' then 'Kobrasol'

                -- Joinville neighborhoods
                when 'america' then 'América'
                when 'aventureiro' then 'Aventureiro'
                when 'bucarein' then 'Bucarein'

                -- Blumenau neighborhoods
                when 'itoupava' then 'Itoupava'
                when 'victor_konder' then 'Victor Konder'

                -- Itajaí neighborhoods
                when 'saojoao' then 'São João'
                when 'fazenda' then 'Fazenda'

                -- Tubarão neighborhoods
                when 'oficinas' then 'Oficinas'
                when 'vila_moema' then 'Vila Moema'

                -- Criciúma neighborhoods
                when 'santa_barbara' then 'Santa Bárbara'
                when 'centenario' then 'Centenário'

                -- Palhoça neighborhoods
                when 'passavinte' then 'Passa Vinte'
                when 'pagani' then 'Pagani'

                -- Default: Title case the neighborhood code
                else upper(replace(neighborhood_code, '_', ' '))
            end as neighborhood_name

        from parsed_locations
    )

    , with_state_info as (
        select
            *
            -- State code based on city (SC or RS)
            , case
                when city_code in ('poa', 'canoas', 'torres', 'tramandai', 'capao_da_canoa')
                then 'RS'
                else 'SC'
            end as state_code

            -- Country code (all Brazil for now)
            , 'BR' as country_code

        from with_city_names
    )

    , with_surrogate_key as (
        select
            row_number() over (order by location_id) as location_key  -- Surrogate key
            , location_id  -- Natural key (e.g., 'florianopolis_costeira')

            -- Geographic hierarchy
            , city_name
            , city_code
            , neighborhood_name
            , neighborhood_code

            -- State and country
            , state_code
            , country_code

            -- Geocoding placeholders (future enhancement via API)
            , null::decimal(9,6) as latitude
            , null::decimal(9,6) as longitude

            -- Metadata
            , current_timestamp as created_at
            , current_timestamp as updated_at

        from with_state_info
    )

select * from with_surrogate_key
