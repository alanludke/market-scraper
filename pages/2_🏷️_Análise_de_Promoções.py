"""
Promotions Analysis Dashboard Page
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Análise de Promoções", page_icon="🏷️", layout="wide")

# Database connection (use centralized db_manager)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dashboard.utils.db_manager import get_duckdb_connection

@st.cache_resource
def get_conn():
    return get_duckdb_connection()

st.title("🏷️ Análise de Promoções")
st.markdown("---")

conn = get_conn()

# Filters
st.subheader("🔍 Filtros")
col1, col2 = st.columns(2)

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

st.markdown("---")

# Promotion Summary
st.subheader("📊 Resumo de Promoções por Loja")

promo_summary = conn.execute(f"""
SELECT
    supermarket,
    products_on_promotion,
    round(avg_discount_pct, 1) as avg_discount,
    round(promotion_penetration_pct, 1) as penetration_pct,
    hot_deal_products
FROM dev_local.fct_promotion_summary
WHERE supermarket IN ({','.join([f"'{s}'" for s in selected_stores])})
ORDER BY supermarket, avg_discount DESC
""").df()

# Map store_ids to store_names for display
store_name_map = dict(zip(stores['store_id'], stores['store_name']))
promo_summary['supermarket_name'] = promo_summary['supermarket'].map(store_name_map)

# Aggregate by store (average across regions)
promo_by_store = promo_summary.groupby('supermarket_name').agg({
    'products_on_promotion': 'mean',
    'avg_discount': 'mean',
    'penetration_pct': 'mean',
    'hot_deal_products': 'mean'
}).reset_index()

col1, col2 = st.columns(2)

with col1:
    fig_penetration = px.bar(
        promo_by_store,
        x='supermarket_name',
        y='penetration_pct',
        title="Penetração de Promoções (%)",
        labels={'penetration_pct': 'Penetração (%)', 'supermarket_name': 'Loja'},
        color='penetration_pct',
        text='penetration_pct'
    )
    fig_penetration.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_penetration, use_container_width=True)

with col2:
    fig_discount = px.bar(
        promo_by_store,
        x='supermarket_name',
        y='avg_discount',
        title="Desconto Médio (%)",
        labels={'avg_discount': 'Desconto Médio (%)', 'supermarket_name': 'Loja'},
        color='avg_discount',
        text='avg_discount'
    )
    fig_discount.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_discount, use_container_width=True)

# Hot Deals (>30% discount)
st.markdown("---")
st.subheader("🔥 Hot Deals (Descontos > 30%)")

# Get latest scrape date for freshness indicator
latest_date = conn.execute("""
    SELECT max(dd.date_day) as latest
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
""").fetchone()[0]

st.info(f"📅 **Última atualização:** {latest_date} | ✅ Dados válidos para hoje")

hot_deals = conn.execute(f"""
SELECT
    ap.product_id,
    ap.product_name,
    ap.brand,
    ds.store_name as supermarket,
    dr.city_name || ' - ' || dr.neighborhood_code as region,
    round(ap.promotional_price, 2) as promo_price,
    round(ap.regular_price, 2) as regular_price,
    round(ap.discount_percentage, 1) as discount_pct,
    ap.promotion_type,
    dd.date_day as data_extracao,
    -- Construct product URL (if available from tru_product)
    (SELECT product_url FROM dev_local.tru_product tp
     WHERE tp.product_id = ap.product_id
       AND tp.supermarket = ds.store_id
     LIMIT 1) as product_url
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
WHERE ap.discount_percentage >= 30
    AND ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
ORDER BY ap.discount_percentage DESC
LIMIT 50
""").df()

if len(hot_deals) > 0:
    # Add clickable links
    if 'product_url' in hot_deals.columns:
        hot_deals['link'] = hot_deals.apply(
            lambda row: f'<a href="{row["product_url"]}" target="_blank">🔗 Ver produto</a>' if pd.notna(row['product_url']) else 'N/A',
            axis=1
        )

    # Display with HTML links
    st.markdown(hot_deals.to_html(escape=False, index=False), unsafe_allow_html=True)

    # Also provide download button
    st.download_button(
        label="⬇️ Baixar Hot Deals (CSV)",
        data=hot_deals.drop('link', axis=1, errors='ignore').to_csv(index=False).encode('utf-8'),
        file_name=f"hot_deals_{latest_date}.csv",
        mime="text/csv"
    )
else:
    st.info("Nenhum hot deal disponível no momento.")

# Discount Distribution
st.markdown("---")
st.subheader("📊 Distribuição de Descontos")

discount_dist = conn.execute(f"""
SELECT
    promotion_type,
    count(*) as product_count
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
GROUP BY promotion_type
ORDER BY product_count DESC
""").df()

fig_discount_dist = px.pie(
    discount_dist,
    names='promotion_type',
    values='product_count',
    title="Distribuição de Produtos por Tipo de Promoção"
)
st.plotly_chart(fig_discount_dist, use_container_width=True)

# Top Brands on Promotion
st.markdown("---")
st.subheader("🏆 Marcas Mais Promocionadas")

top_brands_promo = conn.execute(f"""
SELECT
    brand,
    count(DISTINCT product_id) as products_on_promo,
    round(avg(discount_percentage), 1) as avg_discount
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
WHERE brand IS NOT NULL
    AND ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
    AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
GROUP BY brand
ORDER BY products_on_promo DESC
LIMIT 15
""").df()

fig_brands = px.bar(
    top_brands_promo,
    x='brand',
    y='products_on_promo',
    title="Top 15 Marcas com Mais Produtos em Promoção",
    labels={'products_on_promo': 'Produtos em Promoção', 'brand': 'Marca'},
    color='avg_discount',
    text='products_on_promo'
)
fig_brands.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_brands, use_container_width=True)

# Summary metrics
st.markdown("---")
st.subheader("📊 Estatísticas Gerais")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_promo = conn.execute(f"""
        SELECT count(*)
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
        WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    """).fetchone()[0]
    st.metric("Total de Promoções", f"{total_promo:,}")

with col2:
    avg_discount_all = conn.execute(f"""
        SELECT round(avg(discount_percentage), 1)
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
        WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    """).fetchone()[0]
    st.metric("Desconto Médio", f"{avg_discount_all}%")

with col3:
    hot_deals_count = conn.execute(f"""
        SELECT count(*)
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
        WHERE discount_percentage >= 30
            AND ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    """).fetchone()[0]
    st.metric("Hot Deals (>30%)", f"{hot_deals_count:,}")

with col4:
    max_discount = conn.execute(f"""
        SELECT round(max(discount_percentage), 1)
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
        WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
            AND dr.region_code IN ({','.join([f"'{r}'" for r in selected_regions])})
    """).fetchone()[0]
    st.metric("Maior Desconto", f"{max_discount}%")
