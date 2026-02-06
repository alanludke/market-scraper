/*
    Location-Based Analysis Examples

    Demonstrates insights enabled by dim_location and dim_store_location.
    These queries were NOT possible before consolidating locations.
*/

-- ============================================================================
-- 1. CROSS-STORE PRICE COMPARISON IN SAME NEIGHBORHOOD
-- ============================================================================
-- Compare prices of Bistek vs Fort vs Giassi in the SAME location
--
-- Use case: "Is Bistek cheaper than Fort in Florianópolis - Costeira?"

with
    products_in_location as (
        select
            dp.product_name
            , l.city_name
            , l.neighborhood_name
            , s.store_name
            , round(avg(dp.min_price), 2) as avg_price
        from dev_local.fct_daily_prices dp
        join dev_local.dim_store s on dp.store_key = s.store_key
        join dev_local.dim_region dr on dp.region_key = dr.region_key
        join dev_local.dim_location l on dr.region_code = l.location_id
        where l.location_id = 'florianopolis_costeira'  -- Same location
          and dp.min_price > 0
        group by dp.product_name, l.city_name, l.neighborhood_name, s.store_name
    )

select
    product_name
    , city_name || ' - ' || neighborhood_name as location
    , store_name
    , avg_price
    , rank() over (partition by product_name order by avg_price) as price_rank
from products_in_location
order by product_name, avg_price
limit 100;


-- ============================================================================
-- 2. COVERAGE GAP ANALYSIS
-- ============================================================================
-- Which stores are NOT present in which cities?
--
-- Use case: "Where should Giassi expand to compete with Bistek?"

with
    all_cities as (
        select distinct
            city_name
            , state_code
        from dev_local.dim_location
    )

    , store_presence as (
        select
            l.city_name
            , s.store_name
            , count(distinct sl.location_key) as locations_in_city
        from dev_local.dim_store s
        cross join all_cities c
        left join dev_local.dim_store_location sl
            on s.store_key = sl.store_key
        left join dev_local.dim_location l
            on sl.location_key = l.location_key
            and c.city_name = l.city_name
        group by l.city_name, s.store_name, c.city_name
    )

select
    city_name
    , store_name
    , case
        when locations_in_city > 0 then 'Presente (' || locations_in_city || ' lojas)'
        else 'AUSENTE - Oportunidade de expansão'
    end as status
from store_presence
where city_name is not null
order by city_name, store_name;


-- ============================================================================
-- 3. PRICE HEATMAP BY NEIGHBORHOOD
-- ============================================================================
-- Average price by neighborhood (for geospatial visualization)
--
-- Use case: "Which neighborhoods are most expensive?"

select
    l.city_name
    , l.neighborhood_name
    , l.state_code
    , count(distinct dp.product_key) as products
    , round(avg(dp.min_price), 2) as avg_price
    , round(min(dp.min_price), 2) as min_price
    , round(max(dp.min_price), 2) as max_price
    -- Geocoding placeholders (will be populated via API)
    , l.latitude
    , l.longitude
from dev_local.fct_daily_prices dp
join dev_local.dim_region dr on dp.region_key = dr.region_key
join dev_local.dim_location l on dr.region_code = l.location_id
where dp.min_price > 0
group by l.city_name, l.neighborhood_name, l.state_code, l.latitude, l.longitude
order by avg_price desc
limit 50;


-- ============================================================================
-- 4. STORE DENSITY BY CITY
-- ============================================================================
-- How many stores (and which ones) are in each city?
--
-- Use case: "Which cities have the most competition?"

select
    l.city_name
    , l.state_code
    , count(distinct sl.store_key) as total_stores
    , string_agg(distinct s.store_name, ', ' order by s.store_name) as stores_present
    , count(distinct sl.location_key) as total_locations
from dev_local.dim_location l
left join dev_local.dim_store_location sl on l.location_key = sl.location_key
left join dev_local.dim_store s on sl.store_key = s.store_key
group by l.city_name, l.state_code
order by total_stores desc, total_locations desc;


-- ============================================================================
-- 5. COMPETITIVE INTENSITY BY NEIGHBORHOOD
-- ============================================================================
-- Which neighborhoods have multiple stores competing?
--
-- Use case: "Where is competition most intense?"

with
    neighborhood_competition as (
        select
            l.location_id
            , l.city_name
            , l.neighborhood_name
            , count(distinct sl.store_key) as competing_stores
            , string_agg(distinct s.store_name, ' vs ' order by s.store_name) as competitors
        from dev_local.dim_location l
        join dev_local.dim_store_location sl on l.location_key = sl.location_key
        join dev_local.dim_store s on sl.store_key = s.store_key
        group by l.location_id, l.city_name, l.neighborhood_name
    )

select
    city_name
    , neighborhood_name
    , competing_stores
    , competitors
    , case
        when competing_stores >= 3 then 'Alta competição'
        when competing_stores = 2 then 'Competição média'
        else 'Monopólio local'
    end as competition_level
from neighborhood_competition
order by competing_stores desc, city_name, neighborhood_name;


-- ============================================================================
-- 6. PRICE VARIATION WITHIN SAME CITY
-- ============================================================================
-- How much do prices vary across neighborhoods in the same city?
--
-- Use case: "Should I drive to another neighborhood for better prices?"

with
    city_neighborhood_prices as (
        select
            l.city_name
            , l.neighborhood_name
            , dp.product_name
            , round(avg(dp.min_price), 2) as avg_price
        from dev_local.fct_daily_prices dp
        join dev_local.dim_region dr on dp.region_key = dr.region_key
        join dev_local.dim_location l on dr.region_code = l.location_id
        where dp.min_price > 0
        group by l.city_name, l.neighborhood_name, dp.product_name
    )

    , price_stats as (
        select
            city_name
            , product_name
            , min(avg_price) as cheapest_neighborhood_price
            , max(avg_price) as most_expensive_neighborhood_price
            , round((max(avg_price) - min(avg_price)) / nullif(min(avg_price), 0) * 100, 1) as price_spread_pct
        from city_neighborhood_prices
        group by city_name, product_name
        having count(distinct neighborhood_name) >= 2  -- At least 2 neighborhoods
    )

select
    city_name
    , product_name
    , cheapest_neighborhood_price
    , most_expensive_neighborhood_price
    , price_spread_pct
from price_stats
where price_spread_pct > 20  -- More than 20% difference
order by price_spread_pct desc
limit 100;
