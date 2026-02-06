"""
Price Analysis Dashboard Page
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Análise de Preços", page_icon="💰", layout="wide")

# Database connection
@st.cache_resource
def get_conn():
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "analytics.duckdb"
    return duckdb.connect(str(db_path), read_only=True)

st.title("💰 Análise de Preços")
st.markdown("---")

conn = get_conn()

# Filters
st.subheader("🔍 Filtros")
col1, col2, col3 = st.columns(3)

with col1:
    stores = conn.execute("SELECT DISTINCT store_id, store_name FROM dev_local.dim_store ORDER BY store_name").df()
    selected_stores = st.multiselect(
        "Lojas:",
        options=stores['store_id'].tolist(),
        default=stores['store_id'].tolist(),
        format_func=lambda x: stores[stores['store_id'] == x]['store_name'].iloc[0] if len(stores[stores['store_id'] == x]) > 0 else x
    )

with col2:
    regions = conn.execute("""
        SELECT DISTINCT region_code, city_name
        FROM dev_local.dim_region
        ORDER BY city_name, region_code
    """).df()
    selected_regions = st.multiselect(
        "Regiões:",
        options=regions['region_code'].tolist(),
        default=regions['region_code'].tolist(),
        format_func=lambda x: f"{regions[regions['region_code'] == x]['city_name'].iloc[0]} - {x.split('_')[1] if '_' in x else x}" if len(regions[regions['region_code'] == x]) > 0 else x
    )

with col3:
    categories = conn.execute("""
        SELECT DISTINCT brand_name
        FROM dev_local.dim_brand
        WHERE brand_name IS NOT NULL
        ORDER BY brand_name
        LIMIT 50
    """).df()
    selected_brand = st.selectbox(
        "Marca (opcional):",
        options=["Todas"] + categories['brand_name'].tolist()
    )

st.markdown("---")

# Price Distribution
st.subheader("📊 Distribuição de Preços por Loja")

price_dist_query = f"""
SELECT
    ds.store_name as supermarket,
    dp.min_price
FROM dev_local.fct_daily_prices dp
JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
JOIN dev_local.dim_region dr ON dp.region_key = dr.region_key
WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    AND dp.min_price BETWEEN 1 AND 500
"""

if selected_brand != "Todas":
    price_dist_query += f" AND dp.brand = '{selected_brand}'"

price_dist = conn.execute(price_dist_query).df()

fig_dist = px.box(
    price_dist,
    x='supermarket',
    y='min_price',
    title="Distribuição de Preços por Loja",
    labels={'min_price': 'Preço (R$)', 'supermarket': 'Loja'},
    color='supermarket'
)
st.plotly_chart(fig_dist, use_container_width=True)

# Price Comparison Table
st.subheader("🔍 Comparação de Preços - Top Produtos")

top_products_query = f"""
SELECT
    dp.product_name,
    ds.store_name as supermarket,
    round(dp.min_price, 2) as price,
    round(dp.discount_pct, 1) as discount_pct,
    dp.is_available,
    dd.date_day as data_extracao
FROM dev_local.fct_daily_prices dp
JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
JOIN dev_local.dim_region dr ON dp.region_key = dr.region_key
JOIN dev_local.dim_date dd ON dp.date_key = dd.date_key
WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    AND dp.min_price > 0
"""

if selected_brand != "Todas":
    top_products_query += f" AND dp.brand = '{selected_brand}'"

top_products_query += """
ORDER BY dp.min_price DESC
LIMIT 100
"""

top_products = conn.execute(top_products_query).df()
st.dataframe(top_products, use_container_width=True, height=400)

# Price Index by Store
st.subheader("📈 Índice de Preços por Loja")

price_index_query = f"""
SELECT
    ds.store_name as supermarket,
    round(avg(dp.min_price), 2) as avg_price,
    round(min(dp.min_price), 2) as min_price,
    round(max(dp.min_price), 2) as max_price,
    count(DISTINCT dp.product_key) as product_count
FROM dev_local.fct_daily_prices dp
JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
JOIN dev_local.dim_region dr ON dp.region_key = dr.region_key
WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
GROUP BY ds.store_name
ORDER BY avg_price
"""

price_index = conn.execute(price_index_query).df()

fig_index = px.bar(
    price_index,
    x='supermarket',
    y='avg_price',
    title="Preço Médio por Loja",
    labels={'avg_price': 'Preço Médio (R$)', 'supermarket': 'Loja'},
    color='avg_price',
    text='avg_price'
)
fig_index.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
st.plotly_chart(fig_index, use_container_width=True)

# Summary metrics
st.markdown("---")
st.subheader("📊 Estatísticas Resumidas")

col1, col2, col3 = st.columns(3)

with col1:
    total_products = conn.execute(f"""
        SELECT count(DISTINCT product_key)
        FROM dev_local.fct_daily_prices dp
        JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON dp.region_key = dr.region_key
        WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    """).fetchone()[0]
    st.metric("Total de Produtos", f"{total_products:,}")

with col2:
    avg_price_all = conn.execute(f"""
        SELECT round(avg(min_price), 2)
        FROM dev_local.fct_daily_prices dp
        JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON dp.region_key = dr.region_key
        WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
            AND min_price > 0
    """).fetchone()[0]
    st.metric("Preço Médio Geral", f"R$ {avg_price_all:.2f}")

with col3:
    cheapest_store = price_index.iloc[0]['supermarket'] if len(price_index) > 0 else "N/A"
    st.metric("Loja Mais Barata (média)", cheapest_store)
