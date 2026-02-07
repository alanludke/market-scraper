{#
    Model: dim_store
    Layer: Gold - Conformed Dimensions

    Description:
        Store dimension with attributes for retail location analysis.
        Includes store name, type, and operational metadata.

    Grain: supermarket (one row per store)

    Business Logic:
        - One record per supermarket chain
        - Store type classification (hypermarket, supermarket, wholesale)
        - Operational status and metadata

    Lineage: Hardcoded seed data (will become source when store master table exists)
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension']
    )
}}

with
    stores_seed as (
        select * from (
            values
                ('bistek', 'Bistek Supermercados', 'supermarket', 'SC/RS', true, 13, 'https://www.bistek.com.br'),
                ('fort', 'Fort Atacadista', 'wholesale', 'SC', true, 7, 'https://www.fortatacadista.com.br'),
                ('giassi', 'Giassi Supermercados', 'hypermarket', 'SC', true, 17, 'https://www.giassi.com.br'),
                ('carrefour', 'Carrefour', 'hypermarket', 'SC', true, 5, 'https://mercado.carrefour.com.br'),
                ('angeloni', 'Angeloni', 'supermarket', 'SC/PR', true, 3, 'https://www.angeloni.com.br')
        ) as t(store_id, store_name, store_type, coverage_states, is_active, region_count, website_url)
    )

    , stores_with_keys as (
        select
            -- Surrogate key
            row_number() over (order by store_id) as store_key

            -- Natural key
            , store_id

            -- Attributes
            , store_name
            , store_type
            , coverage_states
            , is_active
            , region_count
            , website_url

            -- Classification
            , case store_type
                when 'hypermarket' then 'Large format (>2500m²)'
                when 'supermarket' then 'Medium format (500-2500m²)'
                when 'wholesale' then 'Cash & carry format'
                else 'Unknown'
            end as store_type_description

            -- Business segment
            , case
                when store_type in ('hypermarket', 'supermarket') then 'B2C'
                when store_type = 'wholesale' then 'B2B/B2C'
                else 'Unknown'
            end as business_segment

        from stores_seed
    )

select
    *
    , current_timestamp as loaded_at
from stores_with_keys
