{#
    Macro: generate_schema_name

    Gera nome do schema baseado no target (padrão Indicium).

    Lógica:
    - Prod/CI: Usa custom_schema_name se definido (ex: pricing_marts, trusted)
    - Dev: Usa target.schema (ex: dev_alan, permitindo isolamento por dev)

    Baseado em: indimesh_dbt_core_reference/macros/general_config/generate_schema_name.sql
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if target.name in ('prod', 'ci') and custom_schema_name is not none -%}
        {# Prod/CI: usa schema customizado (ex: pricing_marts, trusted) #}
        {{ custom_schema_name | trim }}

    {%- else -%}
        {# Dev: usa target.schema (ex: dev_alan) para isolamento #}
        {{ default_schema }}

    {%- endif -%}

{%- endmacro %}
