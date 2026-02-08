{#
    Model: vw_suspicious_hot_deals
    Layer: Gold - Pricing Marts (View)

    Description:
        View of suspicious hot-deals flagged for manual review.

        Flags deals that may be:
        - Fake/inflated anchor pricing (>70% discount)
        - Data quality issues (invalid prices)
        - Flash deals (appeared only once - may be errors)

    Use cases:
        - Data quality monitoring
        - Manual validation of extreme deals
        - Fraud detection
        - Price scraping error detection

    Lineage: fct_hot_deals_validated → vw_suspicious_hot_deals
#}

{{
    config(
        materialized='view',
        tags=['pricing', 'view', 'quality', 'monitoring']
    )
}}

with
    suspicious_deals as (
        select
            product_id
            , product_name
            , brand
            , supermarket
            , region
            , scraped_date
            , promotional_price
            , regular_price
            , discount_percentage
            , absolute_discount
            , quality_score
            , legitimacy_level
            , is_suspicious_discount
            , has_invalid_price
            , is_flash_deal
            , deal_persistence_days
            , is_available

            -- Reason flags
            , case when is_suspicious_discount then '🚨 Extreme Discount (>70%)' else '' end as flag_extreme_discount
            , case when has_invalid_price then '❌ Invalid Pricing' else '' end as flag_invalid_price
            , case when is_flash_deal then '⚡ Flash Deal (1 day)' else '' end as flag_flash_deal
            , case when quality_score < 50 then '⚠️  Low Quality Score' else '' end as flag_low_quality

            -- Combined reason
            , concat_ws(', ',
                case when is_suspicious_discount then '🚨 Extreme Discount (>70%)' end,
                case when has_invalid_price then '❌ Invalid Pricing' end,
                case when is_flash_deal then '⚡ Flash Deal (1 day)' end,
                case when quality_score < 50 then '⚠️  Low Quality Score' end
            ) as suspicious_reasons

        from {{ ref('fct_hot_deals_validated') }}
        where
            legitimacy_level = 'Suspicious'
            or is_suspicious_discount = true
            or has_invalid_price = true
            or (is_flash_deal = true and discount_percentage > 50)  -- High discount flash deals are very suspicious
            or quality_score < 30  -- Very low quality
    )

    , with_severity as (
        select
            *

            -- Severity scoring (1-10, 10 = most suspicious)
            , (
                case when is_suspicious_discount then 5 else 0 end
                + case when has_invalid_price then 4 else 0 end
                + case when is_flash_deal and discount_percentage > 50 then 3 else 0 end
                + case when quality_score < 30 then 2 else 0 end
            ) as suspicion_severity

            -- Priority for review
            , case
                when is_suspicious_discount and is_flash_deal then 'CRITICAL'
                when is_suspicious_discount or has_invalid_price then 'HIGH'
                when is_flash_deal and discount_percentage > 50 then 'MEDIUM'
                else 'LOW'
            end as review_priority

        from suspicious_deals
    )

select
    -- Identifiers
    product_id
    , product_name
    , brand
    , supermarket
    , region
    , scraped_date

    -- Pricing
    , promotional_price
    , regular_price
    , discount_percentage
    , absolute_discount

    -- Quality metrics
    , quality_score
    , legitimacy_level
    , deal_persistence_days
    , is_available

    -- Suspicion details
    , suspicious_reasons
    , suspicion_severity
    , review_priority

    -- Individual flags
    , is_suspicious_discount
    , has_invalid_price
    , is_flash_deal

    , current_timestamp as reviewed_at

from with_severity
order by
    review_priority,
    suspicion_severity desc,
    discount_percentage desc
