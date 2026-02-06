"""
Market Scraper Dashboard - Main Application
=============================================

Streamlit multi-page dashboard for visualizing supermarket price data.

Architecture:
- Main app.py: Landing page with navigation
- pages/: Individual analysis pages (prices, promotions, competitiveness)
- utils.py: Shared utilities (DuckDB connection, data loading, plotting)

Usage:
    streamlit run src/dashboard/app.py
"""

import streamlit as st
import duckdb
from pathlib import Path

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
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Database connection (use db_manager for smart loading)
from dashboard.utils.db_manager import get_duckdb_connection

# Load summary metrics
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_summary_metrics():
    """Load high-level KPIs for overview."""
    conn = get_duckdb_connection()

    metrics = {}

    # Total products
    metrics['total_products'] = conn.execute("""
        SELECT count(DISTINCT product_id) FROM dev_local.tru_product
    """).fetchone()[0]

    # Total stores
    metrics['total_stores'] = conn.execute("""
        SELECT count(DISTINCT supermarket) FROM dev_local.tru_product
    """).fetchone()[0]

    # Total regions
    metrics['total_regions'] = conn.execute("""
        SELECT count(DISTINCT region) FROM dev_local.tru_product
    """).fetchone()[0]

    # Average price
    metrics['avg_price'] = conn.execute("""
        SELECT round(avg(min_price), 2) FROM dev_local.tru_product WHERE min_price > 0
    """).fetchone()[0]

    # Products on promotion
    metrics['products_on_promo'] = conn.execute("""
        SELECT count(DISTINCT product_id) FROM dev_local.fct_active_promotions
    """).fetchone()[0]

    # Average discount
    metrics['avg_discount'] = conn.execute("""
        SELECT round(avg(discount_percentage), 2) FROM dev_local.fct_active_promotions
    """).fetchone()[0]

    # Latest scrape date
    metrics['latest_scrape'] = conn.execute("""
        SELECT max(scraped_date) FROM dev_local.tru_product
    """).fetchone()[0]

    return metrics

# Main app
def main():
    """Main landing page."""

    st.markdown('<div class="main-header">🛒 Market Scraper Analytics</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Load metrics
    with st.spinner("Carregando dados..."):
        metrics = load_summary_metrics()

    # KPI Cards
    st.subheader("📊 Visão Geral")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total de Produtos",
            value=f"{metrics['total_products']:,}",
            delta=None
        )

    with col2:
        st.metric(
            label="Lojas Monitoradas",
            value=metrics['total_stores'],
            delta=None
        )

    with col3:
        st.metric(
            label="Regiões Cobertas",
            value=metrics['total_regions'],
            delta=None
        )

    with col4:
        st.metric(
            label="Preço Médio",
            value=f"R$ {metrics['avg_price']:.2f}",
            delta=None
        )

    st.markdown("---")

    # Promotion metrics
    st.subheader("🏷️ Promoções Ativas")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Produtos em Promoção",
            value=f"{metrics['products_on_promo']:,}",
            delta=None
        )

    with col2:
        promo_pct = (metrics['products_on_promo'] / metrics['total_products']) * 100
        st.metric(
            label="Penetração de Promoções",
            value=f"{promo_pct:.1f}%",
            delta=None
        )

    with col3:
        st.metric(
            label="Desconto Médio",
            value=f"{metrics['avg_discount']:.1f}%",
            delta=None
        )

    st.markdown("---")

    # Data freshness
    st.info(f"📅 Última atualização: **{metrics['latest_scrape']}**")

    # Navigation guide
    st.markdown("---")
    st.subheader("🧭 Navegação")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 💰 Análise de Preços
        - Evolução temporal de preços
        - Comparação entre lojas
        - Índice de preços por região

        👉 **Acesse na barra lateral**
        """)

    with col2:
        st.markdown("""
        ### 🏷️ Análise de Promoções
        - Hot deals (>30% desconto)
        - Produtos mais descontados
        - Calendário promocional

        👉 **Acesse na barra lateral**
        """)

    with col3:
        st.markdown("""
        ### 🥊 Competitividade
        - Price gap entre lojas
        - Produtos multi-store
        - Loja mais barata por produto

        👉 **Acesse na barra lateral**
        """)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666;">
        <p>Market Scraper Analytics v2.0 | Desenvolvido com ❤️ usando Streamlit + DuckDB + DBT</p>
        <p>Dados atualizados diariamente via scrapers VTEX</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
