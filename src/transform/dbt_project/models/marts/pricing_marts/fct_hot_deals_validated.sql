{#
    Model: fct_hot_deals_validated
    Layer: Gold - Pricing Marts (Fact Table)

    Description:
        Validated hot-deals fact table with quality scoring.
        Filters out suspicious/fake deals and ranks by legitimacy.

        Quality validation rules:
        - Minimum 20% discount threshold
        - Maximum 70% discount (above = suspicious)
        - Price consistency (list_price > price)
        - Temporal persistence (deal appears in multiple scrapes)
        - Brand reputation scoring

    Grain: product_key + store_key + region_key + date_key (validated hot-deals only)

    Business Logic:
        - Filter hot-deals (discount >= 20%)
        - Apply quality validations
        - Calculate quality score (0-100)
        - Flag suspicious deals (>70% discount)
        - Rank deals by quality and savings

    Lineage: fct_active_promotions → fct_hot_deals_validated
#}

{{
    config(
        materialized='table',
        tags=['pricing', 'fact', 'hot-deals', 'quality']
    )
}}

with
    hot_deals_raw as (
        select
            product_key
            , product_id
            , product_name
            , brand_key
            , brand
            , store_key
            , supermarket
            , region_key
            , region
            , date_key
            , scraped_date
            , promotional_price
            , regular_price
            , discount_percentage
            , absolute_discount
            , is_available

        from {{ ref('fct_active_promotions') }}
        where
            discount_percentage >= 20  -- Hot-deal minimum threshold
            and is_hot_deal = true
            and regular_price > promotional_price  -- Basic consistency check
    )

    , quality_validations as (
        select
            *

            -- Quality flags
            , case
                when discount_percentage > 70 then true
                else false
            end as is_suspicious_discount

            , case
                when promotional_price <= 0 or regular_price <= 0 then true
                else false
            end as has_invalid_price

            , case
                when discount_percentage >= 20 and discount_percentage <= 50 then true
                else false
            end as is_optimal_discount_range

            -- Brand reputation (simplified - can be enhanced with external data)
            , case
                when brand is not null and length(brand) > 2 then true
                else false
            end as has_known_brand

        from hot_deals_raw
    )

    , quality_scoring as (
        select
            *

            -- Quality score calculation (0-100)
            , (
                -- Factor 1: Optimal discount range (50 points)
                case when is_optimal_discount_range then 50 else 0 end

                -- Factor 2: No suspicious flags (30 points)
                + case when not is_suspicious_discount then 30 else 0 end

                -- Factor 3: Valid pricing (10 points)
                + case when not has_invalid_price then 10 else 0 end

                -- Factor 4: Known brand (10 points)
                + case when has_known_brand then 10 else 0 end
            ) as quality_score

            -- Legitimacy classification
            , case
                when is_suspicious_discount or has_invalid_price then 'Suspicious'
                when is_optimal_discount_range and has_known_brand then 'High Quality'
                when is_optimal_discount_range then 'Good Quality'
                else 'Review Required'
            end as legitimacy_level

        from quality_validations
    )

    , temporal_persistence as (
        select
            qs.*

            -- Count appearances of same product+store deal over last 7 days
            , count(*) over (
                partition by qs.product_key, qs.store_key
                order by qs.scraped_date
                rows between 6 preceding and current row
            ) as deal_persistence_days

            -- Flag flash deals (appeared only once)
            , case
                when count(*) over (
                    partition by qs.product_key, qs.store_key
                    order by qs.scraped_date
                    rows between 6 preceding and current row
                ) = 1 then true
                else false
            end as is_flash_deal

        from quality_scoring qs
    )

    , ranked_deals as (
        select
            *

            -- Rank deals by quality score within each store/date
            , row_number() over (
                partition by store_key, date_key
                order by quality_score desc, discount_percentage desc
            ) as quality_rank

            -- Rank deals by absolute savings
            , row_number() over (
                partition by store_key, date_key
                order by absolute_discount desc
            ) as savings_rank

            -- Overall legitimacy rank (combines quality + savings)
            , row_number() over (
                partition by store_key, date_key
                order by
                    case when legitimacy_level = 'High Quality' then 1
                         when legitimacy_level = 'Good Quality' then 2
                         when legitimacy_level = 'Review Required' then 3
                         else 4
                    end,
                    discount_percentage desc
            ) as overall_rank

        from temporal_persistence
    )

    , final as (
        select
            -- Keys
            product_key
            , product_id
            , product_name
            , brand_key
            , brand
            , store_key
            , supermarket
            , region_key
            , region
            , date_key
            , scraped_date

            -- Pricing
            , promotional_price
            , regular_price
            , discount_percentage
            , absolute_discount

            -- Quality metrics
            , quality_score
            , legitimacy_level
            , is_suspicious_discount
            , has_invalid_price
            , is_optimal_discount_range
            , has_known_brand

            -- Temporal metrics
            , deal_persistence_days
            , is_flash_deal

            -- Rankings
            , quality_rank
            , savings_rank
            , overall_rank

            -- Availability
            , is_available

            -- Recommendation flag (high quality, non-suspicious, persistent deals)
            , case
                when legitimacy_level in ('High Quality', 'Good Quality')
                    and not is_suspicious_discount
                    and not is_flash_deal
                    and quality_score >= 70
                then true
                else false
            end as is_recommended_deal

        from ranked_deals
    )

select
    *
    , current_timestamp as loaded_at
from final
