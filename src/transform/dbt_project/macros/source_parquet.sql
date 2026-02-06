{#
    Macro: source_parquet

    Description:
        Generates a read_parquet() call for bronze Parquet sources.
        Works around dbt-duckdb's limitation with external table definitions.

    Usage:
        {{ source_parquet('bronze_bistek', 'products') }}

    Generates:
        read_parquet('data/bronze/supermarket=bistek/**/*.parquet', hive_partitioning=1)
#}

{% macro source_parquet(source_name, table_name) %}

    {%- set parquet_paths = {
        'bronze_bistek': '../../../data/bronze/supermarket=bistek/region=*/year=*/month=*/day=*/run_*/*_full.parquet',
        'bronze_fort': '../../../data/bronze/supermarket=fort/region=*/year=*/month=*/day=*/run_*/*_full.parquet',
        'bronze_giassi': '../../../data/bronze/supermarket=giassi/region=*/year=*/month=*/day=*/run_*/*_full.parquet'
    } -%}

    {%- set path = parquet_paths.get(source_name) -%}

    {%- if not path -%}
        {{ exceptions.raise_compiler_error("Unknown source: " ~ source_name) }}
    {%- endif -%}

    read_parquet('{{ path }}', hive_partitioning=1)

{% endmacro %}
