"""
Competitiveness Analysis Dashboard Page
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
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
st.markdown("Comparação de preços entre supermercados")
st.markdown("---")

conn = get_conn()

# Filters
st.subheader("🔍 Filtros")
col1, col2 = st.columns(2)

with col1:
    stores_filter = conn.execute("SELECT DISTINCT store_name FROM dev_local.dim_store WHERE is_active = true ORDER BY store_name").df()
    selected_stores = st.multiselect(
        "Selecione Lojas",
        options=stores_filter['store_name'].tolist(),
        default=stores_filter['store_name'].tolist()
    )

with col2:
    min_products = st.slider("Mínimo de lojas com produto", 2, 4, 2)

st.markdown("---")

# Build store filter SQL
if selected_stores:
    store_filter_sql = "AND s.store_name IN ('" + "', '".join(selected_stores) + "')"
else:
    store_filter_sql = ""

# Multi-store products using tru_product directly (better query)
st.subheader("📊 Produtos Disponíveis em Múltiplas Lojas")

multi_store = conn.execute(f"""
WITH product_stores AS (
    SELECT
        p.product_name,
        p.ean,
        s.store_name,
        MIN(p.min_price) as price
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON p.supermarket = s.store_id
    WHERE p.min_price > 0
        AND p.scraped_date >= CURRENT_DATE - INTERVAL 7 DAY
        {store_filter_sql}
    GROUP BY p.product_name, p.ean, s.store_name
)
SELECT
    product_name,
    ean,
    COUNT(DISTINCT store_name) as store_count,
    MIN(price) as lowest_price,
    MAX(price) as highest_price,
    ROUND(MAX(price) - MIN(price), 2) as price_spread,
    ROUND(((MAX(price) - MIN(price)) / NULLIF(MIN(price), 0)) * 100, 1) as price_spread_pct,
    LIST(DISTINCT store_name) as stores
FROM product_stores
GROUP BY product_name, ean
HAVING COUNT(DISTINCT store_name) >= {min_products}
ORDER BY price_spread_pct DESC
LIMIT 100
""").df()

if not multi_store.empty:
    # Format currency columns
    multi_store['lowest_price'] = multi_store['lowest_price'].apply(lambda x: f"R$ {x:.2f}")
    multi_store['highest_price'] = multi_store['highest_price'].apply(lambda x: f"R$ {x:.2f}")
    multi_store['price_spread'] = multi_store['price_spread'].apply(lambda x: f"R$ {x:.2f}")
    # Format stores list to string
    multi_store['stores'] = multi_store['stores'].apply(lambda x: ', '.join(sorted(x)) if isinstance(x, list) else str(x))

    st.dataframe(
        multi_store.rename(columns={
            'product_name': 'Produto',
            'ean': 'EAN',
            'store_count': 'Lojas',
            'lowest_price': 'Menor Preço',
            'highest_price': 'Maior Preço',
            'price_spread': 'Diferença',
            'price_spread_pct': 'Diferença (%)',
            'stores': 'Disponível em'
        }),
        use_container_width=True,
        height=400
    )
else:
    st.info("🔍 Nenhum produto encontrado em múltiplas lojas com os filtros selecionados.")

# Price leadership analysis
st.markdown("---")
st.subheader("🏆 Liderança de Preços por Loja")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Quem tem mais produtos mais baratos?**")

    store_wins = conn.execute(f"""
    WITH product_prices AS (
        SELECT
            p.product_name,
            p.ean,
            s.store_name,
            MIN(p.min_price) as price
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON p.supermarket = s.store_id
        WHERE p.min_price > 0
            AND p.scraped_date >= CURRENT_DATE - INTERVAL 7 DAY
            {store_filter_sql}
        GROUP BY p.product_name, p.ean, s.store_name
    ),
    cheapest_per_product AS (
        SELECT
            product_name,
            ean,
            MIN(price) as min_price
        FROM product_prices
        GROUP BY product_name, ean
        HAVING COUNT(DISTINCT store_name) >= {min_products}
    )
    SELECT
        pp.store_name,
        COUNT(*) as times_cheapest,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as win_rate_pct
    FROM product_prices pp
    JOIN cheapest_per_product cpp ON pp.product_name = cpp.product_name AND pp.ean = cpp.ean
    WHERE pp.price = cpp.min_price
    GROUP BY pp.store_name
    ORDER BY times_cheapest DESC
    """).df()

    if not store_wins.empty:
        fig_wins = px.bar(
            store_wins,
            y='store_name',
            x='win_rate_pct',
            orientation='h',
            text='win_rate_pct',
            labels={'win_rate_pct': 'Taxa de Liderança (%)', 'store_name': ''},
            color='win_rate_pct',
            color_continuous_scale='Greens'
        )
        fig_wins.update_traces(texttemplate='%{text}%', textposition='outside')
        fig_wins.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig_wins, use_container_width=True)
    else:
        st.info("Sem dados disponíveis")

with col2:
    st.markdown("**Média de preços por loja**")

    avg_prices = conn.execute(f"""
    SELECT
        s.store_name,
        ROUND(AVG(p.min_price), 2) as avg_price,
        COUNT(DISTINCT p.product_id) as product_count
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON p.supermarket = s.store_id
    WHERE p.min_price > 0
        AND p.scraped_date >= CURRENT_DATE - INTERVAL 7 DAY
        {store_filter_sql}
    GROUP BY s.store_name
    ORDER BY avg_price ASC
    """).df()

    if not avg_prices.empty:
        fig_avg = px.bar(
            avg_prices,
            y='store_name',
            x='avg_price',
            orientation='h',
            text='avg_price',
            labels={'avg_price': 'Preço Médio (R$)', 'store_name': ''},
            color='avg_price',
            color_continuous_scale='RdYlGn_r'
        )
        fig_avg.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
        fig_avg.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig_avg, use_container_width=True)
    else:
        st.info("Sem dados disponíveis")

# Top opportunities
st.markdown("---")
st.subheader("💎 Maiores Oportunidades de Economia")
st.markdown("Produtos com maior diferença de preço entre lojas")

top_gaps = conn.execute(f"""
WITH product_prices AS (
    SELECT
        p.product_name,
        p.ean,
        s.store_name,
        MIN(p.min_price) as price
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON p.supermarket = s.store_id
    WHERE p.min_price > 0
        AND p.scraped_date >= CURRENT_DATE - INTERVAL 7 DAY
        {store_filter_sql}
    GROUP BY p.product_name, p.ean, s.store_name
),
price_ranges AS (
    SELECT
        product_name,
        ean,
        MIN(price) as min_price,
        MAX(price) as max_price,
        MAX(price) - MIN(price) as spread,
        COUNT(DISTINCT store_name) as store_count
    FROM product_prices
    GROUP BY product_name, ean
    HAVING COUNT(DISTINCT store_name) >= {min_products}
)
SELECT
    pr.product_name,
    pr.ean,
    pr.min_price,
    pr.max_price,
    ROUND(pr.spread, 2) as spread,
    ROUND((pr.spread / NULLIF(pr.min_price, 0)) * 100, 1) as spread_pct,
    pr.store_count
FROM price_ranges pr
ORDER BY pr.spread DESC
LIMIT 15
""").df()

if not top_gaps.empty:
    fig_opp = go.Figure()

    # Add bars for price range
    fig_opp.add_trace(go.Bar(
        name='Preço Mínimo',
        y=top_gaps['product_name'],
        x=top_gaps['min_price'],
        orientation='h',
        marker=dict(color='lightgreen'),
        text=top_gaps['min_price'].apply(lambda x: f'R$ {x:.2f}'),
        textposition='inside'
    ))

    fig_opp.add_trace(go.Bar(
        name='Spread',
        y=top_gaps['product_name'],
        x=top_gaps['spread'],
        orientation='h',
        marker=dict(color='lightcoral'),
        text=top_gaps['spread_pct'].apply(lambda x: f'+{x}%'),
        textposition='inside'
    ))

    fig_opp.update_layout(
        barmode='stack',
        xaxis_title="Preço (R$)",
        yaxis_title="",
        height=500,
        showlegend=True
    )

    st.plotly_chart(fig_opp, use_container_width=True)
else:
    st.info("Sem dados disponíveis")

st.markdown("---")
st.caption("💡 **Insights**: Produtos com maior spread de preço (%) representam as melhores oportunidades para economizar escolhendo a loja certa.")
