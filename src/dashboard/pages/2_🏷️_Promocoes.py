"""
Análise de Promoções - Market Scraper Dashboard
================================================

Análise estratégica de promoções: ROI, hot deals, matriz amplitude vs profundidade,
evolução temporal e oportunidades de economia.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, date

# Must be first Streamlit command
st.set_page_config(
    page_title="Análise de Promoções",
    page_icon="🏷️",
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
        border-left: 5px solid #2ca02c;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .insight-box {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ff7f0e;
        margin: 1rem 0;
    }
    .hot-deal {
        background-color: #ffebee;
        padding: 0.5rem;
        border-radius: 0.3rem;
        border-left: 3px solid #f44336;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🏷️ Análise de Promoções")
st.markdown("Inteligência estratégica de promoções e oportunidades de economia")
st.markdown("---")

# Database connection
conn = get_duckdb_connection()

# ========== SIDEBAR FILTERS ==========
# Date range filter (using shared utility)
start_date, end_date = render_date_filter()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros Adicionais")

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

# Discount threshold
discount_threshold = st.sidebar.slider(
    "Desconto mínimo (%)",
    min_value=0,
    max_value=100,
    value=10,
    step=5,
    help="Filtrar apenas promoções com desconto maior que este valor"
)

# Hot deal threshold
hot_deal_threshold = st.sidebar.number_input(
    "Hot Deal threshold (%)",
    min_value=20,
    max_value=100,
    value=30,
    step=5,
    help="Desconto mínimo para considerar um 'Hot Deal'"
)

# ========== DATA LOADING ==========

@st.cache_data(ttl=300)
def load_promo_data(start_date, end_date, stores_list, min_discount, hot_threshold):
    """Load comprehensive promotion analysis data."""

    stores_filter = "'" + "','".join(stores_list) + "'"
    date_filter = get_date_filter_sql(start_date, end_date, date_column='ap.scraped_date')

    data = {}

    # Overall promotion metrics
    data['metrics'] = conn.execute(f"""
        SELECT
            COUNT(DISTINCT ap.product_id) as total_promos,
            ROUND(AVG(ap.discount_percentage), 1) as avg_discount,
            ROUND(SUM(ap.regular_price - ap.promotional_price), 2) as total_savings,
            COUNT(DISTINCT CASE WHEN ap.discount_percentage >= {hot_threshold} THEN ap.product_id END) as hot_deals
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
    """).fetchone()

    # Promotion by store
    data['by_store'] = conn.execute(f"""
        SELECT
            ds.store_name,
            COUNT(DISTINCT ap.product_id) as promo_count,
            ROUND(AVG(ap.discount_percentage), 1) as avg_discount,
            ROUND(SUM(ap.regular_price - ap.promotional_price), 2) as total_savings,
            COUNT(DISTINCT CASE WHEN ap.discount_percentage >= {hot_threshold} THEN ap.product_id END) as hot_deals
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
        GROUP BY ds.store_name
        ORDER BY promo_count DESC
    """).df()

    # Discount distribution
    data['discount_distribution'] = conn.execute(f"""
        SELECT
            CASE
                WHEN discount_percentage < 10 THEN '0-10%'
                WHEN discount_percentage < 20 THEN '10-20%'
                WHEN discount_percentage < 30 THEN '20-30%'
                WHEN discount_percentage < 40 THEN '30-40%'
                WHEN discount_percentage < 50 THEN '40-50%'
                ELSE '50%+'
            END as discount_range,
            COUNT(*) as count
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
        GROUP BY discount_range
        ORDER BY discount_range
    """).df()

    # Top hot deals
    data['hot_deals'] = conn.execute(f"""
        SELECT
            ap.product_name,
            ds.store_name,
            ap.regular_price,
            ap.promotional_price,
            ap.discount_percentage,
            (ap.regular_price - ap.promotional_price) as savings
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {hot_threshold}
        ORDER BY ap.discount_percentage DESC
        LIMIT 50
    """).df()

    # Strategic matrix: Amplitude (promo count) vs Depth (avg discount)
    data['strategic_matrix'] = conn.execute(f"""
        SELECT
            ds.store_name,
            COUNT(DISTINCT ap.product_id) as promo_amplitude,
            ROUND(AVG(ap.discount_percentage), 1) as promo_depth
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
        GROUP BY ds.store_name
    """).df()

    # Best savings opportunities (highest absolute savings)
    data['best_savings'] = conn.execute(f"""
        SELECT
            ap.product_name,
            ds.store_name,
            ap.regular_price,
            ap.promotional_price,
            ap.discount_percentage,
            (ap.regular_price - ap.promotional_price) as savings
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
        ORDER BY savings DESC
        LIMIT 30
    """).df()

    # Brand breakdown
    data['by_brand'] = conn.execute(f"""
        SELECT
            ap.brand,
            COUNT(DISTINCT ap.product_id) as promo_count,
            ROUND(AVG(ap.discount_percentage), 1) as avg_discount,
            ROUND(SUM(ap.regular_price - ap.promotional_price), 2) as total_savings
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE {date_filter}
            AND ds.store_name IN ({stores_filter})
            AND ds.is_active = true
            AND ap.discount_percentage >= {min_discount}
            AND ap.brand IS NOT NULL
        GROUP BY ap.brand
        ORDER BY promo_count DESC
        LIMIT 20
    """).df()

    return data

# Load data
if not selected_stores:
    st.warning("⚠️ Selecione pelo menos uma loja nos filtros")
    st.stop()

with st.spinner("⏳ Carregando análise de promoções..."):
    data = load_promo_data(start_date, end_date, selected_stores, discount_threshold, hot_deal_threshold)

# ========== SECTION 1: KEY METRICS ==========
st.subheader("📊 Métricas Principais")

metrics = data['metrics']

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Produtos em Promoção",
        f"{metrics[0]:,}",
        help="Total de produtos com desconto ativo"
    )

with col2:
    st.metric(
        "Desconto Médio",
        f"{metrics[1]:.1f}%",
        help="Profundidade média dos descontos"
    )

with col3:
    st.metric(
        "Economia Potencial",
        f"R$ {metrics[2]:,.2f}",
        help="Total que pode ser economizado comprando tudo em promoção"
    )

with col4:
    st.metric(
        f"🔥 Hot Deals (≥{hot_deal_threshold}%)",
        f"{metrics[3]:,}",
        help=f"Produtos com desconto acima de {hot_deal_threshold}%"
    )

st.markdown("---")

# ========== SECTION 2: STORE COMPARISON ==========
st.subheader("🏪 Comparação por Loja")

col1, col2 = st.columns(2)

with col1:
    # Promo count by store
    if not data['by_store'].empty:
        fig_store_count = px.bar(
            data['by_store'],
            y='store_name',
            x='promo_count',
            orientation='h',
            text='promo_count',
            color='promo_count',
            color_continuous_scale='Greens',
            labels={'promo_count': 'Produtos em Promoção', 'store_name': 'Loja'}
        )
        fig_store_count.update_traces(textposition='outside')
        fig_store_count.update_layout(
            title="Volume de Promoções por Loja",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_store_count, width="stretch")

with col2:
    # Average discount by store
    if not data['by_store'].empty:
        fig_store_discount = px.bar(
            data['by_store'],
            y='store_name',
            x='avg_discount',
            orientation='h',
            text='avg_discount',
            color='avg_discount',
            color_continuous_scale='Oranges',
            labels={'avg_discount': 'Desconto Médio (%)', 'store_name': 'Loja'}
        )
        fig_store_discount.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_store_discount.update_layout(
            title="Profundidade Média de Desconto por Loja",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_store_discount, width="stretch")

# Store details table
if not data['by_store'].empty:
    st.markdown("**Detalhes por Loja**")
    display_df = data['by_store'].copy()
    display_df.columns = ['Loja', 'Promoções', 'Desconto Médio (%)', 'Economia Total (R$)', 'Hot Deals']
    st.dataframe(
        display_df.style.format({
            'Promoções': '{:,}',
            'Desconto Médio (%)': '{:.1f}%',
            'Economia Total (R$)': 'R$ {:,.2f}',
            'Hot Deals': '{:,}'
        }),
        width="stretch"
    )

st.markdown("---")

# ========== SECTION 3: STRATEGIC MATRIX ==========
st.subheader("🎯 Matriz Estratégica de Promoções")

st.markdown("""
**Amplitude vs Profundidade**: Identifica diferentes estratégias promocionais
- **Alto volume + Alto desconto**: Estratégia agressiva (market share)
- **Alto volume + Baixo desconto**: Variedade promocional (traffic driver)
- **Baixo volume + Alto desconto**: Promoções seletivas (clearance)
- **Baixo volume + Baixo desconto**: Estratégia conservadora
""")

if not data['strategic_matrix'].empty:
    fig_matrix = px.scatter(
        data['strategic_matrix'],
        x='promo_amplitude',
        y='promo_depth',
        text='store_name',
        size='promo_amplitude',
        color='promo_depth',
        color_continuous_scale='RdYlGn',
        labels={
            'promo_amplitude': 'Amplitude (Nº de Produtos em Promoção)',
            'promo_depth': 'Profundidade (Desconto Médio %)'
        },
        size_max=60
    )
    fig_matrix.update_traces(textposition='top center')
    fig_matrix.update_layout(
        title="Matriz Amplitude vs Profundidade de Promoções",
        height=500
    )
    st.plotly_chart(fig_matrix, width="stretch")

    # Quadrant analysis
    median_amplitude = data['strategic_matrix']['promo_amplitude'].median()
    median_depth = data['strategic_matrix']['promo_depth'].median()

    aggressive = data['strategic_matrix'][
        (data['strategic_matrix']['promo_amplitude'] > median_amplitude) &
        (data['strategic_matrix']['promo_depth'] > median_depth)
    ]

    if not aggressive.empty:
        st.markdown(f"""
        <div class="insight-box">
        💡 <b>Estratégia Agressiva:</b> {', '.join(aggressive['store_name'].tolist())} lidera(m)
        com alta amplitude E profundidade de promoções
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ========== SECTION 4: DISCOUNT DISTRIBUTION ==========
st.subheader("📊 Distribuição de Descontos")

if not data['discount_distribution'].empty:
    # Order discount ranges properly
    range_order = ['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50%+']
    data['discount_distribution']['discount_range'] = pd.Categorical(
        data['discount_distribution']['discount_range'],
        categories=range_order,
        ordered=True
    )
    data['discount_distribution'] = data['discount_distribution'].sort_values('discount_range')

    fig_dist = px.bar(
        data['discount_distribution'],
        x='discount_range',
        y='count',
        text='count',
        color='count',
        color_continuous_scale='Blues',
        labels={'discount_range': 'Faixa de Desconto', 'count': 'Quantidade de Produtos'}
    )
    fig_dist.update_traces(textposition='outside')
    fig_dist.update_layout(
        title="Distribuição de Produtos por Faixa de Desconto",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_dist, width="stretch")

st.markdown("---")

# ========== SECTION 5: HOT DEALS ==========
st.subheader(f"🔥 Hot Deals (≥{hot_deal_threshold}% desconto)")

if not data['hot_deals'].empty:
    st.markdown(f"**{len(data['hot_deals'])} produtos com desconto acima de {hot_deal_threshold}%**")

    # Top 10 highest discount percentage
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🏆 Top 10 Maiores Descontos (%)**")
        top_discount = data['hot_deals'].head(10).copy()
        top_discount.columns = ['Produto', 'Loja', 'Preço Normal', 'Preço Promo', 'Desconto %', 'Economia']
        st.dataframe(
            top_discount.style.format({
                'Preço Normal': 'R$ {:.2f}',
                'Preço Promo': 'R$ {:.2f}',
                'Desconto %': '{:.1f}%',
                'Economia': 'R$ {:.2f}'
            }),
            width="stretch"
        )

    with col2:
        st.markdown("**💰 Top 10 Maiores Economias (R$)**")
        top_savings_hot = data['hot_deals'].nlargest(10, 'savings').copy()
        top_savings_hot.columns = ['Produto', 'Loja', 'Preço Normal', 'Preço Promo', 'Desconto %', 'Economia']
        st.dataframe(
            top_savings_hot.style.format({
                'Preço Normal': 'R$ {:.2f}',
                'Preço Promo': 'R$ {:.2f}',
                'Desconto %': '{:.1f}%',
                'Economia': 'R$ {:.2f}'
            }),
            width="stretch"
        )

    # Full hot deals table (expandable)
    with st.expander(f"📋 Ver todos os {len(data['hot_deals'])} Hot Deals"):
        display_df = data['hot_deals'].copy()
        display_df.columns = ['Produto', 'Loja', 'Preço Normal', 'Preço Promo', 'Desconto %', 'Economia']
        st.dataframe(
            display_df.style.format({
                'Preço Normal': 'R$ {:.2f}',
                'Preço Promo': 'R$ {:.2f}',
                'Desconto %': '{:.1f}%',
                'Economia': 'R$ {:.2f}'
            }),
            width="stretch",
            height=600
        )
else:
    st.info(f"Nenhum produto com desconto ≥ {hot_deal_threshold}% encontrado")

st.markdown("---")

# ========== SECTION 6: BEST SAVINGS OPPORTUNITIES ==========
st.subheader("💎 Maiores Oportunidades de Economia")

if not data['best_savings'].empty:
    st.markdown("**Top 30 produtos onde você economiza mais dinheiro (valor absoluto)**")

    # Chart of top savings
    fig_savings = px.bar(
        data['best_savings'].head(15),
        y='product_name',
        x='savings',
        orientation='h',
        text='savings',
        color='discount_percentage',
        color_continuous_scale='RdYlGn',
        labels={'savings': 'Economia (R$)', 'product_name': 'Produto', 'discount_percentage': 'Desconto %'}
    )
    fig_savings.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
    fig_savings.update_layout(
        title="Top 15 Produtos - Maior Economia Absoluta",
        height=500
    )
    st.plotly_chart(fig_savings, width="stretch")

    # Full table
    display_df = data['best_savings'].copy()
    display_df.columns = ['Produto', 'Loja', 'Preço Normal', 'Preço Promo', 'Desconto %', 'Economia']
    st.dataframe(
        display_df.style.format({
            'Preço Normal': 'R$ {:.2f}',
            'Preço Promo': 'R$ {:.2f}',
            'Desconto %': '{:.1f}%',
            'Economia': 'R$ {:.2f}'
        }),
        width="stretch"
    )

st.markdown("---")

# ========== SECTION 7: BRAND BREAKDOWN ==========
st.subheader("🏷️ Promoções por Marca")

if not data['by_brand'].empty:
    col1, col2 = st.columns([2, 1])

    with col1:
        fig_brand = px.bar(
            data['by_brand'].head(10),
            y='brand',
            x='promo_count',
            orientation='h',
            text='promo_count',
            color='avg_discount',
            color_continuous_scale='Viridis',
            labels={'promo_count': 'Produtos em Promoção', 'brand': 'Marca', 'avg_discount': 'Desconto Médio %'}
        )
        fig_brand.update_traces(textposition='outside')
        fig_brand.update_layout(
            title="Top 10 Marcas com Mais Promoções",
            height=400
        )
        st.plotly_chart(fig_brand, width="stretch")

    with col2:
        st.markdown("**Detalhes por Marca**")
        display_df = data['by_brand'].head(10).copy()
        display_df.columns = ['Marca', 'Promoções', 'Desconto %', 'Economia']
        st.dataframe(
            display_df.style.format({
                'Promoções': '{:,}',
                'Desconto %': '{:.1f}%',
                'Economia': 'R$ {:,.2f}'
            }),
            width="stretch",
            height=400
        )

# Footer
st.markdown("---")
st.caption("💡 Use os filtros na barra lateral para refinar a análise")
