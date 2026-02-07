"""
Análise de Preços - Market Scraper Dashboard
==============================================

Análise detalhada de preços: evolução temporal, distribuição, volatilidade,
comparações entre lojas e identificação de oportunidades.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

# Must be first Streamlit command
st.set_page_config(
    page_title="Análise de Preços",
    page_icon="📈",
    layout="wide"
)

# Import after set_page_config
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.db_manager import get_duckdb_connection

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .insight-box {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2ca02c;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("📈 Análise de Preços")
st.markdown("Inteligência de precificação e oportunidades de economia")
st.markdown("---")

# Database connection
conn = get_duckdb_connection()

# ========== SIDEBAR FILTERS ==========
st.sidebar.header("🔍 Filtros")

# Time range filter
time_range = st.sidebar.selectbox(
    "Período de análise",
    options=[7, 14, 30, 60, 90],
    format_func=lambda x: f"Últimos {x} dias",
    index=1  # Default: 14 days
)

# Store filter
stores = conn.execute("""
    SELECT DISTINCT store_name
    FROM dev_local.dim_store
    WHERE is_active = true
    ORDER BY store_name
""").df()

selected_stores = st.sidebar.multiselect(
    "Lojas",
    options=stores['store_name'].tolist(),
    default=stores['store_name'].tolist()
)

# Price range filter
price_min = st.sidebar.number_input("Preço mínimo (R$)", min_value=0.0, value=0.0, step=1.0)
price_max = st.sidebar.number_input("Preço máximo (R$)", min_value=0.0, value=1000.0, step=10.0)

# ========== DATA LOADING ==========

@st.cache_data(ttl=300)
def load_price_data(days, stores_list, min_price, max_price):
    """Load comprehensive price analysis data."""

    stores_filter = "'" + "','".join(stores_list) + "'"

    data = {}

    # Price statistics
    data['stats'] = conn.execute(f"""
        SELECT
            COUNT(DISTINCT product_id) as total_products,
            ROUND(AVG(min_price), 2) as avg_price,
            ROUND(MEDIAN(min_price), 2) as median_price,
            ROUND(MIN(min_price), 2) as min_price,
            ROUND(MAX(min_price), 2) as max_price,
            ROUND(STDDEV(min_price), 2) as stddev_price
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
    """).fetchone()

    # Daily price evolution
    data['daily_evolution'] = conn.execute(f"""
        SELECT
            scraped_date,
            ROUND(AVG(min_price), 2) as avg_price,
            ROUND(MIN(min_price), 2) as min_price,
            ROUND(MAX(min_price), 2) as max_price,
            COUNT(DISTINCT product_id) as product_count
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        GROUP BY scraped_date
        ORDER BY scraped_date
    """).df()

    # Price distribution by store
    data['store_distribution'] = conn.execute(f"""
        SELECT
            s.store_name,
            ROUND(AVG(p.min_price), 2) as avg_price,
            ROUND(MEDIAN(p.min_price), 2) as median_price,
            ROUND(MIN(p.min_price), 2) as min_price,
            ROUND(MAX(p.min_price), 2) as max_price,
            COUNT(DISTINCT p.product_id) as product_count
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        GROUP BY s.store_name
        ORDER BY avg_price ASC
    """).df()

    # Price histogram
    data['histogram'] = conn.execute(f"""
        SELECT
            FLOOR(min_price / 10) * 10 as price_range,
            COUNT(*) as count
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        GROUP BY price_range
        ORDER BY price_range
    """).df()

    # Top cheapest products
    data['cheapest_products'] = conn.execute(f"""
        SELECT
            p.product_name,
            s.store_name,
            p.min_price,
            p.brand
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        ORDER BY p.min_price ASC
        LIMIT 20
    """).df()

    # Top most expensive products
    data['expensive_products'] = conn.execute(f"""
        SELECT
            p.product_name,
            s.store_name,
            p.min_price,
            p.brand
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        ORDER BY p.min_price DESC
        LIMIT 20
    """).df()

    # Price volatility (coefficient of variation by product)
    data['volatility'] = conn.execute(f"""
        SELECT
            product_name,
            COUNT(DISTINCT scraped_date) as observation_days,
            ROUND(AVG(min_price), 2) as avg_price,
            ROUND(STDDEV(min_price), 2) as stddev_price,
            ROUND((STDDEV(min_price) / NULLIF(AVG(min_price), 0)) * 100, 2) as cv_percent
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.scraped_date >= CURRENT_DATE - INTERVAL '{days}' DAY
            AND p.min_price BETWEEN {min_price} AND {max_price}
            AND s.store_name IN ({stores_filter})
            AND s.is_active = true
        GROUP BY product_name
        HAVING COUNT(DISTINCT scraped_date) >= 3
        ORDER BY cv_percent DESC
        LIMIT 20
    """).df()

    return data

# Load data
if not selected_stores:
    st.warning("⚠️ Selecione pelo menos uma loja nos filtros")
    st.stop()

with st.spinner("⏳ Carregando análise de preços..."):
    data = load_price_data(time_range, selected_stores, price_min, price_max)

# ========== SECTION 1: STATISTICS OVERVIEW ==========
st.subheader("📊 Estatísticas Gerais")

col1, col2, col3, col4, col5, col6 = st.columns(6)

stats = data['stats']

with col1:
    st.metric("Produtos", f"{stats[0]:,}")

with col2:
    st.metric("Preço Médio", f"R$ {stats[1]:.2f}")

with col3:
    st.metric("Mediana", f"R$ {stats[2]:.2f}")

with col4:
    st.metric("Mínimo", f"R$ {stats[3]:.2f}")

with col5:
    st.metric("Máximo", f"R$ {stats[4]:.2f}")

with col6:
    st.metric("Desvio Padrão", f"R$ {stats[5]:.2f}")

st.markdown("---")

# ========== SECTION 2: PRICE EVOLUTION ==========
st.subheader("📈 Evolução Temporal de Preços")

if not data['daily_evolution'].empty:
    fig_evolution = go.Figure()

    # Add average price line
    fig_evolution.add_trace(go.Scatter(
        x=data['daily_evolution']['scraped_date'],
        y=data['daily_evolution']['avg_price'],
        mode='lines+markers',
        name='Preço Médio',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))

    # Add min/max range
    fig_evolution.add_trace(go.Scatter(
        x=data['daily_evolution']['scraped_date'],
        y=data['daily_evolution']['max_price'],
        mode='lines',
        name='Máximo',
        line=dict(color='#ff7f0e', width=1, dash='dash'),
        showlegend=True
    ))

    fig_evolution.add_trace(go.Scatter(
        x=data['daily_evolution']['scraped_date'],
        y=data['daily_evolution']['min_price'],
        mode='lines',
        name='Mínimo',
        line=dict(color='#2ca02c', width=1, dash='dash'),
        fill='tonexty',
        fillcolor='rgba(31, 119, 180, 0.1)',
        showlegend=True
    ))

    fig_evolution.update_layout(
        title="Evolução do Preço Médio (com range min/max)",
        xaxis_title="Data",
        yaxis_title="Preço (R$)",
        hovermode='x unified',
        height=400
    )

    st.plotly_chart(fig_evolution, use_container_width=True)

    # Trend insight
    if len(data['daily_evolution']) >= 2:
        recent_change = data['daily_evolution'].iloc[-1]['avg_price'] - data['daily_evolution'].iloc[0]['avg_price']
        change_pct = (recent_change / data['daily_evolution'].iloc[0]['avg_price']) * 100
        trend = "alta" if recent_change > 0 else "queda"

        st.markdown(f"""
        <div class="insight-box">
        💡 <b>Insight:</b> No período analisado, o preço médio teve {trend} de
        <b>R$ {abs(recent_change):.2f} ({abs(change_pct):.1f}%)</b>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ========== SECTION 3: STORE COMPARISON ==========
st.subheader("🏪 Comparação entre Lojas")

col1, col2 = st.columns(2)

with col1:
    # Average price by store
    if not data['store_distribution'].empty:
        fig_stores = px.bar(
            data['store_distribution'],
            y='store_name',
            x='avg_price',
            orientation='h',
            text='avg_price',
            color='avg_price',
            color_continuous_scale='RdYlGn_r',
            labels={'avg_price': 'Preço Médio (R$)', 'store_name': 'Loja'}
        )
        fig_stores.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
        fig_stores.update_layout(
            title="Preço Médio por Loja",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_stores, use_container_width=True)

with col2:
    # Store statistics table
    if not data['store_distribution'].empty:
        st.markdown("**Estatísticas Detalhadas por Loja**")
        display_df = data['store_distribution'].copy()
        display_df.columns = ['Loja', 'Média', 'Mediana', 'Min', 'Max', 'Produtos']
        st.dataframe(
            display_df.style.format({
                'Média': 'R$ {:.2f}',
                'Mediana': 'R$ {:.2f}',
                'Min': 'R$ {:.2f}',
                'Max': 'R$ {:.2f}',
                'Produtos': '{:,}'
            }),
            use_container_width=True,
            height=400
        )

st.markdown("---")

# ========== SECTION 4: PRICE DISTRIBUTION ==========
st.subheader("📊 Distribuição de Preços")

if not data['histogram'].empty:
    # Create histogram with better labels
    hist_df = data['histogram'].copy()
    hist_df['range_label'] = hist_df['price_range'].apply(lambda x: f"R$ {x:.0f}-{x+10:.0f}")

    fig_hist = px.bar(
        hist_df,
        x='range_label',
        y='count',
        labels={'range_label': 'Faixa de Preço', 'count': 'Quantidade de Produtos'},
        color='count',
        color_continuous_scale='Blues'
    )
    fig_hist.update_layout(
        title="Distribuição de Produtos por Faixa de Preço",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("---")

# ========== SECTION 5: TOP PRODUCTS ==========
st.subheader("🏆 Ranking de Produtos")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**💰 Top 20 Mais Baratos**")
    if not data['cheapest_products'].empty:
        display_df = data['cheapest_products'].copy()
        display_df.columns = ['Produto', 'Loja', 'Preço', 'Marca']
        st.dataframe(
            display_df.style.format({'Preço': 'R$ {:.2f}'}),
            use_container_width=True,
            height=500
        )
    else:
        st.info("Sem dados disponíveis")

with col2:
    st.markdown("**💎 Top 20 Mais Caros**")
    if not data['expensive_products'].empty:
        display_df = data['expensive_products'].copy()
        display_df.columns = ['Produto', 'Loja', 'Preço', 'Marca']
        st.dataframe(
            display_df.style.format({'Preço': 'R$ {:.2f}'}),
            use_container_width=True,
            height=500
        )
    else:
        st.info("Sem dados disponíveis")

st.markdown("---")

# ========== SECTION 6: VOLATILITY ANALYSIS ==========
st.subheader("📉 Análise de Volatilidade")

if not data['volatility'].empty:
    st.markdown("""
    **Coeficiente de Variação (CV)** mede a volatilidade de preços.
    CV alto = preço instável (promoções frequentes ou mudanças de fornecedor).
    """)

    fig_volatility = px.bar(
        data['volatility'].head(15),
        y='product_name',
        x='cv_percent',
        orientation='h',
        text='cv_percent',
        color='cv_percent',
        color_continuous_scale='Reds',
        labels={'cv_percent': 'Coeficiente de Variação (%)', 'product_name': 'Produto'}
    )
    fig_volatility.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_volatility.update_layout(
        title="Top 15 Produtos com Maior Volatilidade de Preço",
        height=500,
        showlegend=False
    )
    st.plotly_chart(fig_volatility, use_container_width=True)

    # Volatility table
    st.markdown("**Detalhes de Volatilidade**")
    display_df = data['volatility'].head(20).copy()
    display_df.columns = ['Produto', 'Dias Observados', 'Preço Médio', 'Desvio Padrão', 'CV (%)']
    st.dataframe(
        display_df.style.format({
            'Preço Médio': 'R$ {:.2f}',
            'Desvio Padrão': 'R$ {:.2f}',
            'CV (%)': '{:.1f}%'
        }),
        use_container_width=True
    )
else:
    st.info("📊 Dados insuficientes para análise de volatilidade (necessário 3+ dias de observação)")

# Footer
st.markdown("---")
st.caption("💡 Use os filtros na barra lateral para refinar a análise")
