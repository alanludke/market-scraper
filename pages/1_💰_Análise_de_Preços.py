"""
Price Analysis Dashboard Page - Strategic Business Intelligence
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Análise de Preços", page_icon="💰", layout="wide")

# Database connection (use centralized db_manager)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dashboard.utils.db_manager import get_duckdb_connection

@st.cache_resource
def get_conn():
    return get_duckdb_connection()

st.title("💰 Análise de Preços")
st.markdown("Inteligência competitiva de precificação")
st.markdown("---")

conn = get_conn()

# Strategic Filters
st.subheader("🎯 Filtros Estratégicos")
col1, col2, col3, col4 = st.columns(4)

with col1:
    stores = conn.execute("SELECT DISTINCT store_name FROM dev_local.dim_store WHERE is_active = true ORDER BY store_name").df()
    selected_stores = st.multiselect(
        "Lojas",
        options=stores['store_name'].tolist(),
        default=stores['store_name'].tolist()
    )

with col2:
    brands = conn.execute("SELECT DISTINCT brand_name FROM dev_local.dim_brand WHERE brand_name IS NOT NULL AND brand_name != '' ORDER BY brand_name LIMIT 50").df()
    selected_brands = st.multiselect(
        "Marcas (top 50)",
        options=brands['brand_name'].tolist(),
        default=[]
    )

with col3:
    days_back = st.slider("Período (dias)", 7, 30, 14)

with col4:
    price_range = st.slider("Faixa de Preço (R$)", 0, 500, (0, 100))

st.markdown("---")

# Build filters
if selected_stores:
    stores_list = "', '".join(selected_stores)
    store_filter = f"AND s.store_name IN ('{stores_list}')"
else:
    store_filter = ""

if selected_brands:
    brands_list = "', '".join(selected_brands)
    brand_filter = f"AND b.brand_name IN ('{brands_list}')"
else:
    brand_filter = ""

price_filter = f"AND p.min_price BETWEEN {price_range[0]} AND {price_range[1]}"
date_filter = f"AND p.scraped_date >= CURRENT_DATE - INTERVAL '{days_back}' DAY"

# KPI Cards
st.subheader("📊 Indicadores-Chave de Preços (KPIs)")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

# KPI 1: Average Price
result = conn.execute(f"""
SELECT ROUND(AVG(p.min_price), 2) as avg_price
FROM dev_local.tru_product p
JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
""").fetchone()
avg_price = result[0] if result and result[0] is not None else 0

# KPI 2: Price Volatility
result = conn.execute(f"""
SELECT ROUND(STDDEV(p.min_price), 2) as volatility
FROM dev_local.tru_product p
JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
""").fetchone()
volatility = result[0] if result and result[0] is not None else 0

# KPI 3: Product Count
result = conn.execute(f"""
SELECT COUNT(DISTINCT p.product_id) as count
FROM dev_local.tru_product p
JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
""").fetchone()
product_count = result[0] if result and result[0] is not None else 0

# KPI 4: Price Change Rate (last 7 days)
price_change = conn.execute(f"""
WITH recent_prices AS (
    SELECT
        p.product_id,
        p.supermarket,
        p.scraped_date,
        p.min_price,
        LAG(p.min_price) OVER (PARTITION BY p.product_id, p.supermarket ORDER BY p.scraped_date) as prev_price
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
    WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
)
SELECT ROUND(AVG(CASE WHEN prev_price > 0 THEN ((min_price - prev_price) / prev_price) * 100 ELSE 0 END), 2) as change_pct
FROM recent_prices
WHERE prev_price IS NOT NULL
""").fetchone()[0] or 0

with kpi_col1:
    st.metric("Preço Médio", f"R$ {avg_price:.2f}" if avg_price else "N/A")

with kpi_col2:
    st.metric("Volatilidade", f"R$ {volatility:.2f}" if volatility else "N/A", help="Desvio padrão dos preços")

with kpi_col3:
    st.metric("Produtos Monitorados", f"{product_count:,}" if product_count else "0")

with kpi_col4:
    delta_color = "inverse" if price_change > 0 else "normal"
    st.metric("Variação Média", f"{price_change:+.2f}%", delta=f"{price_change:+.2f}%", delta_color=delta_color)

st.markdown("---")

# Price Evolution Over Time
st.subheader("📈 Evolução Temporal de Preços")

price_evolution = conn.execute(f"""
SELECT
    p.scraped_date as date,
    s.store_name,
    ROUND(AVG(p.min_price), 2) as avg_price,
    COUNT(DISTINCT p.product_id) as product_count
FROM dev_local.tru_product p
JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
GROUP BY p.scraped_date, s.store_name
ORDER BY p.scraped_date, s.store_name
""").df()

if not price_evolution.empty:
    fig_evolution = px.line(
        price_evolution,
        x='date',
        y='avg_price',
        color='store_name',
        markers=True,
        title="Preço Médio por Loja ao Longo do Tempo",
        labels={'avg_price': 'Preço Médio (R$)', 'date': 'Data', 'store_name': 'Loja'},
        hover_data=['product_count']
    )
    fig_evolution.update_layout(height=400, hovermode='x unified')
    st.plotly_chart(fig_evolution, width='stretch')
else:
    st.info("Sem dados de evolução temporal disponíveis")

# Competitive Price Positioning
st.markdown("---")
st.subheader("🎯 Posicionamento Competitivo de Preços")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Distribuição de Preços por Loja**")

    price_dist = conn.execute(f"""
    SELECT
        s.store_name,
        p.min_price
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
    WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
    """).df()

    if not price_dist.empty:
        fig_box = px.box(
            price_dist,
            x='store_name',
            y='min_price',
            color='store_name',
            title="Distribuição de Preços (Box Plot)",
            labels={'min_price': 'Preço (R$)', 'store_name': 'Loja'},
            points='outliers'
        )
        fig_box.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_box, width='stretch')
    else:
        st.info("Sem dados disponíveis")

with col2:
    st.markdown("**Índice de Preços por Loja**")

    price_index = conn.execute(f"""
    WITH avg_prices AS (
        SELECT
            s.store_name,
            AVG(p.min_price) as avg_price
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
        WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
        GROUP BY s.store_name
    ),
    market_avg AS (
        SELECT AVG(avg_price) as market_avg FROM avg_prices
    )
    SELECT
        ap.store_name,
        ROUND(ap.avg_price, 2) as avg_price,
        ROUND((ap.avg_price / ma.market_avg - 1) * 100, 1) as index_vs_market
    FROM avg_prices ap
    CROSS JOIN market_avg ma
    ORDER BY index_vs_market ASC
    """).df()

    if not price_index.empty:
        # Add color based on index
        price_index['color'] = price_index['index_vs_market'].apply(
            lambda x: 'green' if x < -5 else ('red' if x > 5 else 'orange')
        )

        fig_index = px.bar(
            price_index,
            y='store_name',
            x='index_vs_market',
            orientation='h',
            text='index_vs_market',
            title="Índice de Preços vs Média do Mercado (%)",
            labels={'index_vs_market': 'Diferença vs Mercado (%)', 'store_name': ''},
            color='index_vs_market',
            color_continuous_scale='RdYlGn_r'
        )
        fig_index.update_traces(texttemplate='%{text:+.1f}%', textposition='outside')
        fig_index.update_layout(height=400, showlegend=False)
        fig_index.add_vline(x=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_index, width='stretch')
    else:
        st.info("Sem dados disponíveis")

# Top Products by Price Range
st.markdown("---")
st.subheader("🏆 Top Produtos por Faixa de Preço")

tab1, tab2, tab3 = st.tabs(["💸 Mais Baratos", "💰 Preço Médio", "💎 Premium"])

with tab1:
    cheapest = conn.execute(f"""
    SELECT
        p.product_name,
        s.store_name,
        ROUND(p.min_price, 2) as price,
        b.brand_name
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
    WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
    ORDER BY p.min_price ASC
    LIMIT 20
    """).df()

    if not cheapest.empty:
        st.dataframe(
            cheapest.rename(columns={
                'product_name': 'Produto',
                'store_name': 'Loja',
                'price': 'Preço (R$)',
                'brand_name': 'Marca'
            }),
            width='stretch',
            height=400
        )

with tab2:
    # Products around median price
    median_products = conn.execute(f"""
    WITH price_stats AS (
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY min_price) as median_price
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
        WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
    )
    SELECT
        p.product_name,
        s.store_name,
        ROUND(p.min_price, 2) as price,
        b.brand_name,
        ROUND(ABS(p.min_price - ps.median_price), 2) as distance_from_median
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
    CROSS JOIN price_stats ps
    WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
    ORDER BY distance_from_median ASC
    LIMIT 20
    """).df()

    if not median_products.empty:
        st.dataframe(
            median_products[['product_name', 'store_name', 'price', 'brand_name']].rename(columns={
                'product_name': 'Produto',
                'store_name': 'Loja',
                'price': 'Preço (R$)',
                'brand_name': 'Marca'
            }),
            width='stretch',
            height=400
        )

with tab3:
    premium = conn.execute(f"""
    SELECT
        p.product_name,
        s.store_name,
        ROUND(p.min_price, 2) as price,
        b.brand_name
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    LEFT JOIN dev_local.dim_brand b ON p.brand = b.brand_name
    WHERE p.min_price > 0 {date_filter} {store_filter} {brand_filter} {price_filter}
    ORDER BY p.min_price DESC
    LIMIT 20
    """).df()

    if not premium.empty:
        st.dataframe(
            premium.rename(columns={
                'product_name': 'Produto',
                'store_name': 'Loja',
                'price': 'Preço (R$)',
                'brand_name': 'Marca'
            }),
            width='stretch',
            height=400
        )

st.markdown("---")
st.caption("💡 **Insights Estratégicos**: Use o índice de preços para identificar posicionamento competitivo. Volatilidade alta indica instabilidade de mercado ou sazonalidade.")
