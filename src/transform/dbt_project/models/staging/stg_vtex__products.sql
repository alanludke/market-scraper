{#
    Model: stg_vtex__products
    Layer: Staging (Ephemeral)

    Description:
        Unifica dados brutos de produtos dos 3 supermercados VTEX (Bistek, Fort, Giassi).
        Aplica limpeza básica e padronização de colunas.

    Grain: product_id + region + run_id (raw, sem deduplicação)

    Notes:
        - Ephemeral (não materializa tabela, apenas CTE para downstream models)
        - Sem contracts (staging layer)
        - Dados ainda contêm duplicatas (dedup acontece em trusted layer)
#}

with
    bistek_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items  -- Mantém nested para processar em trusted
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
        from {{ source('bronze_bistek', 'products') }}
        where productId is not null  -- Filtro básico de qualidade
    )

    , fort_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
        from {{ source('bronze_fort', 'products') }}
        where productId is not null
    )

    , giassi_raw as (
        select
            productId as product_id
            , productName as product_name
            , brand
            , link as product_url
            , items
            , _metadata_supermarket as supermarket
            , _metadata_region as region
            , _metadata_postal_code as postal_code
            , _metadata_hub_id as hub_id
            , _metadata_run_id as run_id
            , cast(_metadata_scraped_at as timestamp) as scraped_at
        from {{ source('bronze_giassi', 'products') }}
        where productId is not null
    )

    , unified as (
        select * from bistek_raw
        union all
        select * from fort_raw
        union all
        select * from giassi_raw
    )

select *
from unified
