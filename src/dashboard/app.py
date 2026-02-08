"""
Market Scraper Dashboard - Executive Summary
=============================================

Strategic business intelligence dashboard for supermarket competitive analysis.

Architecture:
- Landing page: Executive KPI dashboard with visual insights
- pages/: Detailed analysis (prices, promotions, competitiveness)
- utils.py: Shared utilities (DuckDB connection, data loading, plotting)

Usage:
    streamlit run app.py
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Market Scraper Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
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

# Database connection
from utils.db_manager import get_duckdb_connection

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_executive_summary():
    """Load comprehensive executive dashboard data."""
    conn = get_duckdb_connection()

    data = {}

    # ========== Core Metrics ==========
    # Total products tracked
    data['total_products'] = conn.execute("""
        SELECT COUNT(DISTINCT product_id) FROM dev_local.tru_product
        WHERE scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
    """).fetchone()[0] or 0

    # Active stores
    data['total_stores'] = conn.execute("""
        SELECT COUNT(DISTINCT store_name) FROM dev_local.dim_store WHERE is_active = true
    """).fetchone()[0] or 0

    # Coverage (regions)
    data['total_regions'] = conn.execute("""
        SELECT COUNT(DISTINCT region_code) FROM dev_local.dim_region
    """).fetchone()[0] or 0

    # Average price
    result = conn.execute("""
        SELECT ROUND(AVG(min_price), 2)
        FROM dev_local.tru_product
        WHERE min_price > 0
            AND scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
    """).fetchone()
    data['avg_price'] = result[0] if result and result[0] else 0

    # ========== Promotion Metrics ==========
    data['products_on_promo'] = conn.execute("""
        SELECT COUNT(DISTINCT product_id) FROM dev_local.fct_active_promotions
    """).fetchone()[0] or 0

    result = conn.execute("""
        SELECT ROUND(AVG(discount_percentage), 1) FROM dev_local.fct_active_promotions
    """).fetchone()
    data['avg_discount'] = result[0] if result and result[0] else 0

    # Hot deals count
    data['hot_deals'] = conn.execute("""
        SELECT COUNT(*) FROM dev_local.fct_active_promotions WHERE discount_percentage >= 30
    """).fetchone()[0] or 0

    # Total potential savings
    result = conn.execute("""
        SELECT ROUND(SUM(regular_price - promotional_price), 2)
        FROM dev_local.fct_active_promotions
    """).fetchone()
    data['total_savings'] = result[0] if result and result[0] else 0

    # ========== Competitive Intelligence ==========
    # Price leader (cheapest on average)
    price_leader = conn.execute("""
        SELECT
            s.store_name,
            ROUND(AVG(p.min_price), 2) as avg_price
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.min_price > 0
            AND p.scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
            AND s.is_active = true
        GROUP BY s.store_name
        ORDER BY avg_price ASC
        LIMIT 1
    """).fetchone()
    data['price_leader'] = price_leader[0] if price_leader else "N/A"
    data['price_leader_avg'] = price_leader[1] if price_leader else 0

    # Promotion leader (most aggressive)
    promo_leader = conn.execute("""
        SELECT
            ds.store_name,
            COUNT(DISTINCT ap.product_id) as promo_count
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE ds.is_active = true
        GROUP BY ds.store_name
        ORDER BY promo_count DESC
        LIMIT 1
    """).fetchone()
    data['promo_leader'] = promo_leader[0] if promo_leader else "N/A"
    data['promo_leader_count'] = promo_leader[1] if promo_leader else 0

    # ========== Trends (Week over Week) ==========
    # Price trend
    price_trend = conn.execute("""
        WITH current_week AS (
            SELECT AVG(min_price) as avg_price
            FROM dev_local.tru_product
            WHERE min_price > 0
                AND scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
        ),
        previous_week AS (
            SELECT AVG(min_price) as avg_price
            FROM dev_local.tru_product
            WHERE min_price > 0
                AND scraped_date >= CURRENT_DATE - INTERVAL '14' DAY
                AND scraped_date < CURRENT_DATE - INTERVAL '7' DAY
        )
        SELECT
            ROUND(((c.avg_price - p.avg_price) / NULLIF(p.avg_price, 0)) * 100, 2) as change_pct
        FROM current_week c, previous_week p
    """).fetchone()
    data['price_trend_pct'] = price_trend[0] if price_trend and price_trend[0] else 0

    # Latest scrape
    latest = conn.execute("""
        SELECT MAX(scraped_date) FROM dev_local.tru_product
    """).fetchone()
    data['latest_scrape'] = latest[0] if latest and latest[0] else "N/A"

    # ========== Charts Data ==========
    # Store price comparison (last 7 days)
    data['store_comparison'] = conn.execute("""
        SELECT
            s.store_name,
            ROUND(AVG(p.min_price), 2) as avg_price,
            COUNT(DISTINCT p.product_id) as product_count
        FROM dev_local.tru_product p
        JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
        WHERE p.min_price > 0
            AND p.scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
            AND s.is_active = true
        GROUP BY s.store_name
        ORDER BY avg_price ASC
    """).df()

    # Daily price evolution (last 14 days)
    data['price_evolution'] = conn.execute("""
        SELECT
            scraped_date,
            ROUND(AVG(min_price), 2) as avg_price
        FROM dev_local.tru_product
        WHERE min_price > 0
            AND scraped_date >= CURRENT_DATE - INTERVAL '14' DAY
        GROUP BY scraped_date
        ORDER BY scraped_date
    """).df()

    # Promotion distribution by store
    data['promo_by_store'] = conn.execute("""
        SELECT
            ds.store_name,
            COUNT(DISTINCT ap.product_id) as products_on_promo,
            ROUND(AVG(ap.discount_percentage), 1) as avg_discount
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE ds.is_active = true
        GROUP BY ds.store_name
        ORDER BY products_on_promo DESC
    """).df()

    return data

# Main app
def main():
    """Executive summary landing page."""

    st.markdown('<div class="main-header">🛒 Market Scraper Analytics</div>', unsafe_allow_html=True)
    st.markdown("**Dashboard Executivo de Inteligência Competitiva**")
    st.markdown("---")

    # Load data
    with st.spinner("⏳ Carregando dados executivos..."):
        data = load_executive_summary()

    # ========== Section 1: Strategic KPIs ==========
    st.subheader("📊 Indicadores Estratégicos")

    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

    with kpi_col1:
        st.metric(
            "Produtos Monitorados",
            f"{data['total_products']:,}",
            help="Total de produtos únicos rastreados (últimos 7 dias)"
        )

    with kpi_col2:
        st.metric(
            "Lojas Ativas",
            data['total_stores'],
            help="Número de supermercados monitorados"
        )

    with kpi_col3:
        st.metric(
            "Cobertura Regional",
            f"{data['total_regions']} regiões",
            help="Número de regiões/bairros cobertos"
        )

    with kpi_col4:
        delta_color = "inverse" if data['price_trend_pct'] > 0 else "normal"
        st.metric(
            "Preço Médio",
            f"R$ {data['avg_price']:.2f}",
            delta=f"{data['price_trend_pct']:+.1f}% vs semana passada",
            delta_color=delta_color,
            help="Preço médio ponderado entre todas as lojas"
        )

    with kpi_col5:
        promo_penetration = (data['products_on_promo'] / max(data['total_products'], 1)) * 100
        st.metric(
            "Taxa de Promoção",
            f"{promo_penetration:.1f}%",
            help="Percentual do catálogo em promoção"
        )

    st.markdown("---")

    # ========== Section 2: Promotion Intelligence ==========
    st.subheader("🏷️ Inteligência de Promoções")

    promo_col1, promo_col2, promo_col3, promo_col4 = st.columns(4)

    with promo_col1:
        st.metric(
            "Produtos em Promoção",
            f"{data['products_on_promo']:,}",
            help="Total de produtos com desconto ativo"
        )

    with promo_col2:
        st.metric(
            "Desconto Médio",
            f"{data['avg_discount']:.1f}%",
            help="Profundidade média dos descontos"
        )

    with promo_col3:
        st.metric(
            "Hot Deals",
            f"{data['hot_deals']:,}",
            help="Produtos com desconto ≥ 30%"
        )

    with promo_col4:
        st.metric(
            "Economia Potencial",
            f"R$ {data['total_savings']:,.2f}",
            help="Total de economia possível comprando tudo em promoção"
        )

    st.markdown("---")

    # ========== Section 3: Competitive Positioning ==========
    st.subheader("🎯 Posicionamento Competitivo")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 💰 Liderança em Preços")
        st.info(f"""
        **{data['price_leader']}** tem o preço médio mais baixo
        📊 **R$ {data['price_leader_avg']:.2f}** (média de produtos)
        """)

        # Store comparison chart
        if not data['store_comparison'].empty:
            fig_stores = px.bar(
                data['store_comparison'],
                y='store_name',
                x='avg_price',
                orientation='h',
                text='avg_price',
                labels={'avg_price': 'Preço Médio (R$)', 'store_name': ''},
                color='avg_price',
                color_continuous_scale='RdYlGn_r',
                title="Comparação de Preços por Loja (últimos 7 dias)"
            )
            fig_stores.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
            fig_stores.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_stores, width="stretch")

    with col2:
        st.markdown("#### 🏷️ Liderança em Promoções")
        st.info(f"""
        **{data['promo_leader']}** tem a estratégia promocional mais agressiva
        📊 **{data['promo_leader_count']:,} produtos** em promoção
        """)

        # Promotion distribution chart
        if not data['promo_by_store'].empty:
            fig_promo = px.bar(
                data['promo_by_store'],
                y='store_name',
                x='products_on_promo',
                orientation='h',
                text='products_on_promo',
                labels={'products_on_promo': 'Produtos em Promoção', 'store_name': ''},
                color='avg_discount',
                color_continuous_scale='Greens',
                title="Volume de Promoções por Loja"
            )
            fig_promo.update_traces(textposition='outside')
            fig_promo.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_promo, width="stretch")

    st.markdown("---")

    # ========== Section 4: Trends ==========
    st.subheader("📈 Tendências de Mercado")

    if not data['price_evolution'].empty:
        fig_trend = px.line(
            data['price_evolution'],
            x='scraped_date',
            y='avg_price',
            markers=True,
            labels={'avg_price': 'Preço Médio (R$)', 'scraped_date': 'Data'},
            title="Evolução do Preço Médio (últimos 14 dias)"
        )
        fig_trend.update_traces(line_color='#1f77b4', line_width=3)
        fig_trend.update_layout(height=350, hovermode='x unified')
        st.plotly_chart(fig_trend, width="stretch")

        # Automated insights
        if len(data['price_evolution']) >= 2:
            recent_change = data['price_evolution'].iloc[-1]['avg_price'] - data['price_evolution'].iloc[-2]['avg_price']
            trend_direction = "subiu" if recent_change > 0 else "caiu"
            st.markdown(f"""
            <div class="insight-box">
            💡 <b>Insight Automatizado:</b> O preço médio {trend_direction} R$ {abs(recent_change):.2f} no último dia de scraping.
            {f"Tendência de alta - possível aumento de custos." if recent_change > 0 else "Tendência de queda - competição por preço ou promoções."}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📊 Dados de tendência insuficientes (necessário 14 dias de histórico)")

    st.markdown("---")

    # ========== Section 5: Data Freshness ==========
    st.info(f"📅 **Última atualização dos dados:** {data['latest_scrape']} | ✅ Dashboard atualizado automaticamente a cada 5 minutos")

    # ========== Section 6: Navigation ==========
    st.markdown("---")
    st.subheader("🧭 Explore Análises Detalhadas")

    nav_col1, nav_col2, nav_col3 = st.columns(3)

    with nav_col1:
        st.markdown("""
        <div class="metric-card">
        <h3>💰 Análise de Preços</h3>
        <ul>
        <li>📈 Evolução temporal de preços</li>
        <li>🎯 Índice de preços vs mercado</li>
        <li>📊 Distribuição e volatilidade</li>
        <li>🏆 Top produtos por faixa</li>
        </ul>
        <p>👉 <b>Acesse na barra lateral</b></p>
        </div>
        """, unsafe_allow_html=True)

    with nav_col2:
        st.markdown("""
        <div class="metric-card">
        <h3>🏷️ Análise de Promoções</h3>
        <ul>
        <li>💎 ROI e economia potencial</li>
        <li>📊 Matriz estratégica (amplitude vs profundidade)</li>
        <li>🔥 Hot Deals (≥30% desconto)</li>
        <li>📈 Evolução temporal</li>
        </ul>
        <p>👉 <b>Acesse na barra lateral</b></p>
        </div>
        """, unsafe_allow_html=True)

    with nav_col3:
        st.markdown("""
        <div class="metric-card">
        <h3>🥊 Competitividade</h3>
        <ul>
        <li>🎯 Price gap entre lojas</li>
        <li>📊 Produtos multi-store</li>
        <li>🏆 Liderança de preços</li>
        <li>💎 Oportunidades de economia</li>
        </ul>
        <p>👉 <b>Acesse na barra lateral</b></p>
        </div>
        """, unsafe_allow_html=True)

    # ========== Footer ==========
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666;">
        <p><b>Market Scraper Analytics v2.0</b> | Desenvolvido com ❤️ usando Streamlit + DuckDB + DBT</p>
        <p>Inteligência competitiva automatizada para supermercados de Florianópolis</p>
        <p style="font-size: 0.8rem;">Arquitetura ELT (Bronze → Silver → Gold) | Dados atualizados diariamente via scrapers VTEX + HTML</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
