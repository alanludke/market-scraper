{#
    Macro: source_parquet

    Description:
        Generates a read_parquet() call for bronze Parquet sources.
        Works around dbt-duckdb's limitation with external table definitions.
        Automatically excludes today's data to avoid conflicts with running scrapers.

    Usage:
        {{ source_parquet('bronze_bistek', 'products') }}

    Generates:
        read_parquet('data/bronze/supermarket=bistek/**/*.parquet', hive_partitioning=1)
        with filter to exclude today's data
#}

{% macro source_parquet(source_name, table_name) %}

    {%- set parquet_paths = {
        'bronze_bistek': '../../../data/bronze/supermarket=bistek/**/*.parquet',
        'bronze_fort': '../../../data/bronze/supermarket=fort/**/*.parquet',
        'bronze_giassi': '../../../data/bronze/supermarket=giassi/**/*.parquet',
        'bronze_carrefour': '../../../data/bronze/supermarket=carrefour/**/*.parquet',
        'bronze_angeloni': '../../../data/bronze/supermarket=angeloni/**/*.parquet',
        'bronze_openfoodfacts': '../../../data/bronze/supermarket=openfoodfacts/**/*.parquet'
    } -%}

    {%- set path = parquet_paths.get(source_name) -%}

    {%- if not path -%}
        {{ exceptions.raise_compiler_error("Unknown source: " ~ source_name) }}
    {%- endif -%}

    (
        select * from read_parquet('{{ path }}', hive_partitioning=1, union_by_name=true)
        where
            -- Exclude Carrefour data from today (still running)
            case
                when supermarket = 'carrefour' then
                    year || '-' || lpad(month::varchar, 2, '0') || '-' || lpad(day::varchar, 2, '0') < current_date::varchar
                else true
            end
    )

{% endmacro %}
