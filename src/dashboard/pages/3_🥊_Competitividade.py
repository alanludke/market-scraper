"""
Análise de Competitividade - Market Scraper Dashboard
======================================================

Análise competitiva de mercado: price gap, liderança de preços, produtos multi-store,
oportunidades de cross-shopping e benchmarking competitivo.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date

# Must be first Streamlit command
st.set_page_config(
    page_title="Análise de Competitividade",
    page_icon="🥊",
    layout="wide"
)

# Import after set_page_config
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.db_manager import get_duckdb_connection
from utils.date_filter import render_date_filter, get_date_filter_sql

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 5px solid #d62728;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .insight-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ff7f0e;
        margin: 1rem 0;
    }
    .winner-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🥊 Análise de Competitividade")
st.markdown("Inteligência competitiva e oportunidades de cross-shopping")
st.markdown("---")

# Database connection
conn = get_duckdb_connection()

# ========== SIDEBAR FILTERS ==========
# Date range filter (using shared utility)
start_date, end_date = render_date_filter()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros Adicionais")

# Minimum stores for cross-store analysis
min_stores = st.sidebar.slider(
    "Mínimo de lojas (produtos multi-store)",
    min_value=2,
    max_value=6,
    value=3,
    help="Analisar apenas produtos presentes em N ou mais lojas"
)

# ========== DATA LOADING ==========

@st.cache_data(ttl=300)
def load_competitive_data(start_date, end_date, min_store_count):
    """Load comprehensive competitive analysis data."""

    date_filter = get_date_filter_sql(start_date, end_date, date_column='p.scraped_date')

    data = {}

    # Overall competitive metrics
    data['metrics'] = conn.execute(f"""
        WITH recent_products AS (
            SELECT DISTINCT
                product_id,
                product_name,
                CAST(supermarket AS VARCHAR) as store_id,
                min_price,
                scraped_date
            FROM dev_local.tru_product p
            WHERE {date_filter}
                AND min_price > 0
        ),
        multi_store_products AS (
            SELECT
                product_name,
                COUNT(DISTINCT store_id) as store_count,
                AVG(min_price) as avg_price,
                MIN(min_price) as min_price,
                MAX(min_price) as max_price
            FROM recent_products
            GROUP BY product_name
            HAVING COUNT(DISTINCT store_id) >= {min_store_count}
        )
        SELECT
            COUNT(*) as multi_store_products,
            ROUND(AVG(max_price - min_price), 2) as avg_price_gap,
            ROUND(MAX(max_price - min_price), 2) as max_price_gap,
            ROUND(AVG((max_price - min_price) / NULLIF(max_price, 0) * 100), 1) as avg_gap_pct
        FROM multi_store_products
    """).fetchone()

    # Store competitive positioning
    data['store_positioning'] = conn.execute(f"""
        SELECT
            s.store_name,
            COUNT(DISTINCT p.product_id) as total_products,
            ROUND(AVG(p.min_price), 2) as avg_price,
            ROUND(MEDIAN(p.min_price), 2) as median_price,
            COUNT(DISTINCT CASE WHEN ap.product_id IS NOT NULL THEN p.product_id END) as products_on_promo
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        LEFT JOIN dev_local.fct_active_promotions ap ON p.product_id = ap.product_id AND p.supermarket = CAST(ap.store_key AS VARCHAR)
        WHERE {date_filter}
            AND p.min_price > 0
            AND s.is_active = true
        GROUP BY s.store_name
        ORDER BY avg_price ASC
    """).df()

    # Multi-store products with biggest price gaps
    data['price_gaps'] = conn.execute(f"""
        WITH recent_products AS (
            SELECT DISTINCT
                p.product_name,
                s.store_name,
                p.min_price,
                p.brand,
                p.scraped_date
            FROM dev_local.tru_product p
            JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
            WHERE {date_filter}
                AND p.min_price > 0
                AND s.is_active = true
        ),
        product_stats AS (
            SELECT
                product_name,
                brand,
                COUNT(DISTINCT store_name) as store_count,
                MIN(min_price) as cheapest_price,
                MAX(min_price) as most_expensive_price,
                (MAX(min_price) - MIN(min_price)) as price_gap,
                ((MAX(min_price) - MIN(min_price)) / NULLIF(MAX(min_price), 0) * 100) as gap_percentage
            FROM recent_products
            GROUP BY product_name, brand
            HAVING COUNT(DISTINCT store_name) >= {min_store_count}
        ),
        cheapest_store AS (
            SELECT
                rp.product_name,
                rp.store_name as cheapest_store,
                rp.min_price
            FROM recent_products rp
            INNER JOIN (
                SELECT product_name, MIN(min_price) as min_price
                FROM recent_products
                GROUP BY product_name
            ) mp ON rp.product_name = mp.product_name AND rp.min_price = mp.min_price
        ),
        expensive_store AS (
            SELECT
                rp.product_name,
                rp.store_name as expensive_store,
                rp.min_price
            FROM recent_products rp
            INNER JOIN (
                SELECT product_name, MAX(min_price) as max_price
                FROM recent_products
                GROUP BY product_name
            ) mp ON rp.product_name = mp.product_name AND rp.min_price = mp.max_price
        )
        SELECT
            ps.product_name,
            ps.brand,
            ps.store_count,
            cs.cheapest_store,
            ps.cheapest_price,
            es.expensive_store,
            ps.most_expensive_price,
            ps.price_gap,
            ROUND(ps.gap_percentage, 1) as gap_percentage
        FROM product_stats ps
        LEFT JOIN cheapest_store cs ON ps.product_name = cs.product_name
        LEFT JOIN expensive_store es ON ps.product_name = es.product_name
        ORDER BY ps.price_gap DESC
        LIMIT 100
    """).df()

    # Price leadership by brand
    data['brand_leaders'] = conn.execute(f"""
        WITH recent_products AS (
            SELECT
                p.brand,
                s.store_name,
                AVG(p.min_price) as avg_price
            FROM dev_local.tru_product p
            JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
            WHERE {date_filter}
                AND p.min_price > 0
                AND s.is_active = true
                AND p.brand IS NOT NULL
            GROUP BY p.brand, s.store_name
        ),
        ranked_stores AS (
            SELECT
                brand,
                store_name,
                avg_price,
                ROW_NUMBER() OVER (PARTITION BY brand ORDER BY avg_price ASC) as rank
            FROM recent_products
        )
        SELECT
            brand,
            store_name as price_leader,
            ROUND(avg_price, 2) as avg_price
        FROM ranked_stores
        WHERE rank = 1
        ORDER BY brand
        LIMIT 20
    """).df()

    # Cross-shopping opportunities (best combo of stores)
    data['cross_shopping'] = conn.execute(f"""
        WITH recent_products AS (
            SELECT DISTINCT
                p.product_name,
                s.store_name,
                p.min_price,
                ROW_NUMBER() OVER (PARTITION BY p.product_name ORDER BY p.min_price ASC) as price_rank
            FROM dev_local.tru_product p
            JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
            WHERE {date_filter}
                AND p.min_price > 0
                AND s.is_active = true
        )
        SELECT
            product_name,
            store_name as best_store,
            min_price as best_price
        FROM recent_products
        WHERE price_rank = 1
        ORDER BY min_price ASC
        LIMIT 50
    """).df()

    # Store win rate (% of times each store has the lowest price)
    data['win_rate'] = conn.execute(f"""
        WITH recent_products AS (
            SELECT DISTINCT
                p.product_name,
                s.store_name,
                p.min_price
            FROM dev_local.tru_product p
            JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
            WHERE {date_filter}
                AND p.min_price > 0
                AND s.is_active = true
        ),
        cheapest_per_product AS (
            SELECT
                product_name,
                MIN(min_price) as cheapest_price
            FROM recent_products
            GROUP BY product_name
        ),
        wins AS (
            SELECT
                rp.store_name,
                COUNT(*) as wins,
                (SELECT COUNT(DISTINCT product_name) FROM recent_products) as total_products
            FROM recent_products rp
            INNER JOIN cheapest_per_product cpp ON rp.product_name = cpp.product_name AND rp.min_price = cpp.cheapest_price
            GROUP BY rp.store_name
        )
        SELECT
            store_name,
            wins,
            ROUND((wins::FLOAT / total_products) * 100, 1) as win_rate_pct
        FROM wins
        ORDER BY win_rate_pct DESC
    """).df()

    # Price index (each store relative to market average)
    data['price_index'] = conn.execute(f"""
        WITH market_avg AS (
            SELECT
                product_name,
                AVG(min_price) as market_avg_price
            FROM dev_local.tru_product p
            WHERE {date_filter}
                AND min_price > 0
            GROUP BY product_name
        ),
        store_prices AS (
            SELECT
                s.store_name,
                p.product_name,
                p.min_price,
                ma.market_avg_price
            FROM dev_local.tru_product p
            JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
            JOIN market_avg ma ON p.product_name = ma.product_name
            WHERE {date_filter}
                AND p.min_price > 0
                AND s.is_active = true
        )
        SELECT
            store_name,
            ROUND(AVG((min_price / market_avg_price) * 100), 1) as price_index
        FROM store_prices
        GROUP BY store_name
        ORDER BY price_index ASC
    """).df()

    return data

# Load data
with st.spinner("⏳ Carregando análise de competitividade..."):
    data = load_competitive_data(start_date, end_date, min_stores)

# ========== SECTION 1: COMPETITIVE OVERVIEW ==========
st.subheader("📊 Visão Geral Competitiva")

metrics = data['metrics']

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Produtos Multi-Store",
        f"{metrics[0]:,}",
        help=f"Produtos presentes em {min_stores}+ lojas"
    )

with col2:
    st.metric(
        "Price Gap Médio",
        f"R$ {metrics[1]:.2f}",
        help="Diferença média de preço entre a loja mais cara e mais barata"
    )

with col3:
    st.metric(
        "Price Gap Máximo",
        f"R$ {metrics[2]:.2f}",
        help="Maior diferença de preço encontrada em um produto"
    )

with col4:
    st.metric(
        "Gap Médio (%)",
        f"{metrics[3]:.1f}%",
        help="Percentual médio de diferença entre preços"
    )

st.markdown("---")

# ========== SECTION 2: STORE POSITIONING ==========
st.subheader("🎯 Posicionamento Competitivo")

if not data['store_positioning'].empty:
    col1, col2 = st.columns([2, 1])

    with col1:
        # Price positioning chart
        fig_positioning = go.Figure()

        fig_positioning.add_trace(go.Bar(
            name='Preço Médio',
            y=data['store_positioning']['store_name'],
            x=data['store_positioning']['avg_price'],
            orientation='h',
            marker_color='#1f77b4',
            text=data['store_positioning']['avg_price'],
            texttemplate='R$ %{text:.2f}',
            textposition='outside'
        ))

        fig_positioning.add_trace(go.Bar(
            name='Mediana',
            y=data['store_positioning']['store_name'],
            x=data['store_positioning']['median_price'],
            orientation='h',
            marker_color='#ff7f0e',
            text=data['store_positioning']['median_price'],
            texttemplate='R$ %{text:.2f}',
            textposition='inside'
        ))

        fig_positioning.update_layout(
            title="Posicionamento de Preços por Loja (Média vs Mediana)",
            xaxis_title="Preço (R$)",
            barmode='group',
            height=400
        )

        st.plotly_chart(fig_positioning, width="stretch")

    with col2:
        st.markdown("**Detalhes por Loja**")
        display_df = data['store_positioning'].copy()
        display_df['promo_rate'] = (display_df['products_on_promo'] / display_df['total_products'] * 100).round(1)
        display_df = display_df[['store_name', 'avg_price', 'total_products', 'promo_rate']]
        display_df.columns = ['Loja', 'Preço Médio', 'Produtos', 'Taxa Promo %']
        st.dataframe(
            display_df.style.format({
                'Preço Médio': 'R$ {:.2f}',
                'Produtos': '{:,}',
                'Taxa Promo %': '{:.1f}%'
            }),
            width="stretch",
            height=400
        )

st.markdown("---")

# ========== SECTION 3: PRICE INDEX ==========
st.subheader("📈 Índice de Preços (Market = 100)")

st.markdown("""
**Price Index** compara cada loja contra a média do mercado:
- **< 100**: Loja mais barata que a média
- **= 100**: Igual à média do mercado
- **> 100**: Loja mais cara que a média
""")

if not data['price_index'].empty:
    # Add reference line at 100
    fig_index = go.Figure()

    fig_index.add_trace(go.Bar(
        y=data['price_index']['store_name'],
        x=data['price_index']['price_index'],
        orientation='h',
        text=data['price_index']['price_index'],
        texttemplate='%{text:.1f}',
        textposition='outside',
        marker_color=data['price_index']['price_index'].apply(
            lambda x: '#2ca02c' if x < 100 else '#d62728'
        )
    ))

    fig_index.add_vline(x=100, line_dash="dash", line_color="gray", annotation_text="Média do Mercado")

    fig_index.update_layout(
        title="Índice de Preços Relativo ao Mercado",
        xaxis_title="Índice (Mercado = 100)",
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig_index, width="stretch")

    # Best value insight
    best_value = data['price_index'].iloc[0]
    st.markdown(f"""
    <div class="winner-box">
    🏆 <b>Melhor Valor:</b> {best_value['store_name']} opera com índice de preço {best_value['price_index']:.1f}
    ({100 - best_value['price_index']:.1f} pontos abaixo da média do mercado)
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ========== SECTION 4: WIN RATE ==========
st.subheader("🏆 Taxa de Vitória (% vezes com menor preço)")

if not data['win_rate'].empty:
    fig_winrate = px.bar(
        data['win_rate'],
        y='store_name',
        x='win_rate_pct',
        orientation='h',
        text='win_rate_pct',
        color='win_rate_pct',
        color_continuous_scale='Greens',
        labels={'win_rate_pct': 'Win Rate (%)', 'store_name': 'Loja'}
    )
    fig_winrate.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_winrate.update_layout(
        title="Percentual de Produtos com Menor Preço do Mercado",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_winrate, width="stretch")

    # Win rate table with absolute numbers
    display_df = data['win_rate'].copy()
    display_df.columns = ['Loja', 'Vitórias', 'Win Rate (%)']
    st.dataframe(
        display_df.style.format({
            'Vitórias': '{:,}',
            'Win Rate (%)': '{:.1f}%'
        }),
        width="stretch"
    )

st.markdown("---")

# ========== SECTION 5: BIGGEST PRICE GAPS ==========
st.subheader(f"💰 Maiores Oportunidades de Economia (Produtos em {min_stores}+ lojas)")

if not data['price_gaps'].empty:
    st.markdown(f"**{len(data['price_gaps'])} produtos com variação significativa de preço**")

    # Top 20 biggest gaps
    col1, col2 = st.columns([2, 1])

    with col1:
        fig_gaps = px.bar(
            data['price_gaps'].head(20),
            y='product_name',
            x='price_gap',
            orientation='h',
            text='price_gap',
            color='gap_percentage',
            color_continuous_scale='Reds',
            labels={'price_gap': 'Diferença de Preço (R$)', 'product_name': 'Produto', 'gap_percentage': 'Gap (%)'}
        )
        fig_gaps.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
        fig_gaps.update_layout(
            title="Top 20 Produtos - Maior Diferença de Preço",
            height=600
        )
        st.plotly_chart(fig_gaps, width="stretch")

    with col2:
        st.markdown("**Onde comprar cada produto**")
        top_gaps = data['price_gaps'].head(20).copy()
        top_gaps_display = top_gaps[['product_name', 'cheapest_store', 'cheapest_price', 'price_gap']]
        top_gaps_display.columns = ['Produto', 'Melhor Loja', 'Menor Preço', 'Economia']
        st.dataframe(
            top_gaps_display.style.format({
                'Menor Preço': 'R$ {:.2f}',
                'Economia': 'R$ {:.2f}'
            }),
            width="stretch",
            height=600
        )

    # Full table (expandable)
    with st.expander(f"📋 Ver todos os {len(data['price_gaps'])} produtos com price gap"):
        display_df = data['price_gaps'].copy()
        display_df.columns = ['Produto', 'Marca', 'Lojas', 'Mais Barato', 'Menor R$', 'Mais Caro', 'Maior R$', 'Gap R$', 'Gap %']
        st.dataframe(
            display_df.style.format({
                'Menor R$': 'R$ {:.2f}',
                'Maior R$': 'R$ {:.2f}',
                'Gap R$': 'R$ {:.2f}',
                'Gap %': '{:.1f}%'
            }),
            width="stretch",
            height=600
        )
else:
    st.info(f"Nenhum produto encontrado em {min_stores}+ lojas. Reduza o filtro 'Mínimo de lojas'.")

st.markdown("---")

# ========== SECTION 6: BRAND PRICE LEADERS ==========
st.subheader("🏅 Liderança de Preço por Marca")

if not data['brand_leaders'].empty:
    st.markdown("**Qual loja tem o menor preço médio em cada marca**")

    # Group by leader to show dominance
    leader_count = data['brand_leaders']['price_leader'].value_counts()

    col1, col2 = st.columns([2, 1])

    with col1:
        # Brand leadership table
        display_df = data['brand_leaders'].copy()
        display_df.columns = ['Marca', 'Líder de Preço', 'Preço Médio']
        st.dataframe(
            display_df.style.format({'Preço Médio': 'R$ {:.2f}'}),
            width="stretch",
            height=500
        )

    with col2:
        # Dominance chart
        fig_dominance = px.pie(
            leader_count.reset_index(),
            values='count',
            names='price_leader',
            title="Distribuição de Liderança por Marca"
        )
        fig_dominance.update_layout(height=500)
        st.plotly_chart(fig_dominance, width="stretch")

    # Dominance insight
    dominant_store = leader_count.index[0]
    dominant_count = leader_count.iloc[0]
    st.markdown(f"""
    <div class="insight-box">
    💡 <b>Insight:</b> {dominant_store} lidera em {dominant_count} marca(s),
    demonstrando forte competitividade em múltiplos segmentos
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ========== SECTION 7: CROSS-SHOPPING STRATEGY ==========
st.subheader("🛒 Estratégia de Cross-Shopping")

st.markdown("""
**Cross-shopping** = comprar cada produto na loja onde ele é mais barato.
Abaixo estão os 50 produtos mais baratos e onde comprá-los.
""")

if not data['cross_shopping'].empty:
    # Group by store to show shopping basket
    basket_by_store = data['cross_shopping'].groupby('best_store').agg({
        'product_name': 'count',
        'best_price': 'sum'
    }).reset_index()
    basket_by_store.columns = ['Loja', 'Produtos', 'Total']
    basket_by_store = basket_by_store.sort_values('Produtos', ascending=False)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Cesta Ideal por Loja (Top 50 produtos)**")
        st.dataframe(
            basket_by_store.style.format({
                'Total': 'R$ {:.2f}'
            }),
            width="stretch"
        )

        total_savings = data['cross_shopping']['best_price'].sum()
        st.metric("Total da Cesta Otimizada", f"R$ {total_savings:.2f}")

    with col2:
        # Product distribution chart
        fig_basket = px.bar(
            basket_by_store,
            x='Loja',
            y='Produtos',
            text='Produtos',
            color='Total',
            color_continuous_scale='Blues',
            labels={'Produtos': 'Quantidade de Produtos', 'Total': 'Valor Total (R$)'}
        )
        fig_basket.update_traces(textposition='outside')
        fig_basket.update_layout(
            title="Distribuição da Cesta Ideal por Loja",
            height=400
        )
        st.plotly_chart(fig_basket, width="stretch")

    # Full cross-shopping list
    with st.expander("📋 Ver lista completa de produtos para cross-shopping"):
        display_df = data['cross_shopping'].copy()
        display_df.columns = ['Produto', 'Melhor Loja', 'Menor Preço']
        st.dataframe(
            display_df.style.format({'Menor Preço': 'R$ {:.2f}'}),
            width="stretch",
            height=600
        )

# Footer
st.markdown("---")
st.caption("💡 Use os filtros na barra lateral para refinar a análise")
