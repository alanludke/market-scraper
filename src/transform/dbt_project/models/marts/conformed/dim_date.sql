{#
    Model: dim_date
    Layer: Gold - Conformed Dimensions

    Description:
        Date dimension with calendar attributes for time-based analysis.
        Standard Kimball date dimension with fiscal calendar support.

    Grain: date (one row per day)

    Business Logic:
        - Generate dates from first scrape to 2 years in future
        - Include day/week/month/quarter/year attributes
        - Support for fiscal calendar (Brazilian retail)
        - Holiday flags and business day indicators

    Lineage: Generated dimension (no source)
#}

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension']
    )
}}

with
    date_spine as (
        -- Generate date range from first scrape to 2 years ahead
        select
            unnest(
                generate_series(
                    date '2026-01-01',
                    current_date + interval '2 years',
                    interval '1 day'
                )
            )::date as date_day
    )

    , date_attributes as (
        select
            date_day

            -- Surrogate key (YYYYMMDD format for easy sorting)
            , cast(strftime(date_day, '%Y%m%d') as integer) as date_key

            -- Day attributes
            , extract(day from date_day) as day_of_month
            , extract(dow from date_day) as day_of_week  -- 0=Sunday, 6=Saturday
            , strftime(date_day, '%A') as day_name
            , strftime(date_day, '%a') as day_name_short
            , extract(doy from date_day) as day_of_year

            -- Week attributes
            , extract(week from date_day) as week_of_year
            , date_trunc('week', date_day)::date as week_start_date
            , (date_trunc('week', date_day) + interval '6 days')::date as week_end_date

            -- Month attributes
            , extract(month from date_day) as month_of_year
            , strftime(date_day, '%B') as month_name
            , strftime(date_day, '%b') as month_name_short
            , date_trunc('month', date_day)::date as month_start_date
            , (date_trunc('month', date_day) + interval '1 month' - interval '1 day')::date as month_end_date
            , strftime(date_day, '%Y-%m') as year_month

            -- Quarter attributes
            , extract(quarter from date_day) as quarter_of_year
            , 'Q' || extract(quarter from date_day) as quarter_name
            , date_trunc('quarter', date_day)::date as quarter_start_date
            , (date_trunc('quarter', date_day) + interval '3 months' - interval '1 day')::date as quarter_end_date

            -- Year attributes
            , extract(year from date_day) as year
            , date_trunc('year', date_day)::date as year_start_date
            , (date_trunc('year', date_day) + interval '1 year' - interval '1 day')::date as year_end_date

            -- Flags
            , case when extract(dow from date_day) in (0, 6) then true else false end as is_weekend
            , case when extract(dow from date_day) between 1 and 5 then true else false end as is_weekday

            -- Brazilian fiscal year (starts April 1st for retail)
            , case
                when extract(month from date_day) >= 4
                    then extract(year from date_day)
                else extract(year from date_day) - 1
            end as fiscal_year

            -- Relative dates
            , case when date_day = current_date then true else false end as is_today
            , case when date_day = current_date - interval '1 day' then true else false end as is_yesterday
            , case when date_day between current_date - interval '7 days' and current_date then true else false end as is_last_7_days
            , case when date_day between current_date - interval '30 days' and current_date then true else false end as is_last_30_days
            , case when date_day between date_trunc('month', current_date) and current_date then true else false end as is_month_to_date
            , case when date_day between date_trunc('year', current_date) and current_date then true else false end as is_year_to_date

        from date_spine
    )

select
    *
    , current_timestamp as loaded_at
from date_attributes
