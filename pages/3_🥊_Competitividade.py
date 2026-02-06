"""
Competitiveness Analysis Dashboard Page
"""

import streamlit as st
import duckdb
import plotly.express as px
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Análise de Competitividade", page_icon="🥊", layout="wide")

# Database connection (use centralized db_manager)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dashboard.utils.db_manager import get_duckdb_connection

@st.cache_resource
def get_conn():
    return get_duckdb_connection()

st.title("🥊 Análise de Competitividade")
st.markdown("---")

conn = get_conn()

# Multi-store products
st.subheader("📊 Produtos Disponíveis em Múltiplas Lojas")

multi_store = conn.execute("""
SELECT
    product_id,
    product_name,
    count(DISTINCT store_key) as store_count,
    min(min_price) as lowest_price,
    max(min_price) as highest_price,
    round((max(min_price) - min(min_price)), 2) as price_spread,
    round(((max(min_price) - min(min_price)) / min(min_price)) * 100, 1) as price_spread_pct
FROM dev_local.fct_price_comparison_v2
GROUP BY product_id, product_name
HAVING count(DISTINCT store_key) >= 2
ORDER BY price_spread_pct DESC
LIMIT 50
""").df()

st.dataframe(multi_store, use_container_width=True, height=400)

# Price gap analysis
st.markdown("---")
st.subheader("💰 Gap de Preços - Mesmos Produtos, Lojas Diferentes")

price_gaps = conn.execute("""
SELECT
    product_name,
    supermarket,
    round(min_price, 2) as price,
    round(lowest_price, 2) as market_lowest,
    round(price_premium_pct, 1) as premium_pct,
    is_cheapest
FROM dev_local.fct_price_comparison_v2
WHERE price_premium_pct > 0
ORDER BY price_premium_pct DESC
LIMIT 30
""").df()

fig_gaps = px.bar(
    price_gaps.head(20),
    x='product_name',
    y='premium_pct',
    color='supermarket',
    title="Top 20 Produtos com Maior Gap de Preço (%)",
    labels={'premium_pct': 'Premium vs Mais Barato (%)', 'product_name': 'Produto'},
    barmode='group'
)
fig_gaps.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_gaps, use_container_width=True)

# Cheapest store ranking
st.markdown("---")
st.subheader("🏆 Ranking de Lojas Mais Baratas")

cheapest_ranking = conn.execute("""
SELECT
    supermarket,
    count(CASE WHEN is_cheapest THEN 1 END) as times_cheapest,
    count(*) as total_comparisons,
    round((count(CASE WHEN is_cheapest THEN 1 END)::float / count(*)) * 100, 1) as win_rate_pct
FROM dev_local.fct_price_comparison_v2
GROUP BY supermarket
ORDER BY win_rate_pct DESC
""").df()

col1, col2 = st.columns(2)

with col1:
    st.dataframe(cheapest_ranking, use_container_width=True)

with col2:
    fig_ranking = px.pie(
        cheapest_ranking,
        names='supermarket',
        values='times_cheapest',
        title="Participação de Produtos Mais Baratos por Loja"
    )
    st.plotly_chart(fig_ranking, use_container_width=True)

# Summary metrics
st.markdown("---")
st.subheader("📊 Estatísticas de Competitividade")

col1, col2, col3, col4 = st.columns(4)

with col1:
    multi_store_count = conn.execute("""
        SELECT count(DISTINCT product_key)
        FROM dev_local.fct_price_comparison_v2
    """).fetchone()[0]
    st.metric("Produtos Multi-Store", f"{multi_store_count:,}")

with col2:
    avg_spread = conn.execute("""
        SELECT round(avg(price_spread_pct), 1)
        FROM (
            SELECT
                product_id,
                ((max(min_price) - min(min_price)) / min(min_price)) * 100 as price_spread_pct
            FROM dev_local.fct_price_comparison_v2
            GROUP BY product_id
        )
    """).fetchone()[0]
    st.metric("Spread Médio de Preços", f"{avg_spread}%")

with col3:
    max_spread = conn.execute("""
        SELECT round(max(price_spread_pct), 1)
        FROM (
            SELECT
                product_id,
                ((max(min_price) - min(min_price)) / min(min_price)) * 100 as price_spread_pct
            FROM dev_local.fct_price_comparison_v2
            GROUP BY product_id
        )
    """).fetchone()[0]
    st.metric("Maior Spread", f"{max_spread}%")

with col4:
    if len(cheapest_ranking) > 0:
        best_store = cheapest_ranking.iloc[0]['supermarket']
        st.metric("Loja Líder em Preço", best_store)
