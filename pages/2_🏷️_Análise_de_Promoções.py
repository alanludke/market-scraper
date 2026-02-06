"""
Promotions Analysis Dashboard Page - Strategic ROI Intelligence
"""

import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Análise de Promoções", page_icon="🏷️", layout="wide")

# Database connection (use centralized db_manager)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dashboard.utils.db_manager import get_duckdb_connection

@st.cache_resource
def get_conn():
    return get_duckdb_connection()

st.title("🏷️ Análise Estratégica de Promoções")
st.markdown("ROI e Inteligência Competitiva de Descontos")
st.markdown("---")

conn = get_conn()

# Strategic Filters
st.subheader("🎯 Filtros Estratégicos")
col1, col2, col3 = st.columns(3)

with col1:
    stores = conn.execute("SELECT DISTINCT store_id, store_name FROM dev_local.dim_store WHERE is_active = true ORDER BY store_name").df()
    selected_stores = st.multiselect(
        "Lojas",
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
        "Regiões",
        options=regions['region_code'].tolist(),
        default=regions['region_code'].tolist(),
        format_func=lambda x: f"{regions[regions['region_code'] == x]['city_name'].iloc[0]} - {x.split('_')[1] if '_' in x else x}" if len(regions[regions['region_code'] == x]) > 0 else x
    )

with col3:
    min_discount = st.slider("Desconto Mínimo (%)", 0, 100, 10)

st.markdown("---")

# Build filters
stores_filter = ','.join([f"'{s}'" for s in selected_stores]) if selected_stores else "''"
regions_filter = ','.join([f"'{r}'" for r in selected_regions]) if selected_regions else "''"

# KPI Cards - ROI Focus
st.subheader("💰 Indicadores de ROI de Promoções")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

# KPI 1: Total Potential Savings
potential_savings = conn.execute(f"""
SELECT ROUND(SUM(ap.regular_price - ap.promotional_price), 2) as total_savings
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
WHERE ds.store_id IN ({stores_filter})
    AND dr.region_code IN ({regions_filter})
    AND ap.discount_percentage >= {min_discount}
""").fetchone()[0] or 0

# KPI 2: Average Discount Depth
avg_discount = conn.execute(f"""
SELECT ROUND(AVG(ap.discount_percentage), 1) as avg_discount
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
WHERE ds.store_id IN ({stores_filter})
    AND dr.region_code IN ({regions_filter})
    AND ap.discount_percentage >= {min_discount}
""").fetchone()[0] or 0

# KPI 3: Promotion Penetration Rate
penetration = conn.execute(f"""
WITH total_products AS (
    SELECT COUNT(DISTINCT p.product_id) as total
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    WHERE s.store_id IN ({stores_filter})
        AND p.scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
),
promo_products AS (
    SELECT COUNT(DISTINCT ap.product_id) as promo
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
)
SELECT ROUND((pp.promo::FLOAT / NULLIF(tp.total, 0)) * 100, 1) as penetration
FROM total_products tp, promo_products pp
""").fetchone()[0] or 0

# KPI 4: Hot Deals Count (>30% discount)
hot_deals_count = conn.execute(f"""
SELECT COUNT(*) as count
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
WHERE ap.discount_percentage >= 30
    AND ds.store_id IN ({stores_filter})
    AND dr.region_code IN ({regions_filter})
""").fetchone()[0] or 0

with kpi_col1:
    st.metric(
        "Economia Potencial Total",
        f"R$ {potential_savings:,.2f}",
        help="Soma de todas as economias possíveis comprando produtos em promoção"
    )

with kpi_col2:
    st.metric(
        "Desconto Médio",
        f"{avg_discount:.1f}%",
        help="Profundidade média dos descontos aplicados"
    )

with kpi_col3:
    st.metric(
        "Taxa de Penetração",
        f"{penetration:.1f}%",
        help="Percentual do catálogo em promoção"
    )

with kpi_col4:
    st.metric(
        "Hot Deals",
        f"{hot_deals_count:,}",
        help="Produtos com desconto ≥ 30%"
    )

st.markdown("---")

# Strategic Positioning: Promotion Strategy Matrix
st.subheader("🎯 Posicionamento Estratégico de Promoções")
st.markdown("**Estratégia de Promoção: Profundidade vs Amplitude**")

strategy_matrix = conn.execute(f"""
WITH store_promo_stats AS (
    SELECT
        ds.store_name,
        COUNT(DISTINCT ap.product_id) as products_on_promo,
        ROUND(AVG(ap.discount_percentage), 1) as avg_discount_depth,
        COUNT(*) FILTER (WHERE ap.discount_percentage >= 30) as aggressive_promos
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
    GROUP BY ds.store_name
),
total_catalog AS (
    SELECT
        s.store_name,
        COUNT(DISTINCT p.product_id) as total_products
    FROM dev_local.tru_product p
    JOIN dev_local.dim_store s ON CAST(p.supermarket AS VARCHAR) = s.store_id
    WHERE s.store_id IN ({stores_filter})
        AND p.scraped_date >= CURRENT_DATE - INTERVAL '7' DAY
    GROUP BY s.store_name
)
SELECT
    sps.store_name,
    sps.products_on_promo,
    sps.avg_discount_depth,
    sps.aggressive_promos,
    ROUND((sps.products_on_promo::FLOAT / NULLIF(tc.total_products, 0)) * 100, 1) as breadth_pct,
    ROUND(sps.products_on_promo * sps.avg_discount_depth / 100, 1) as promo_intensity_score
FROM store_promo_stats sps
LEFT JOIN total_catalog tc ON sps.store_name = tc.store_name
ORDER BY promo_intensity_score DESC
""").df()

if not strategy_matrix.empty:
    # Create scatter plot: Breadth (X) vs Depth (Y)
    fig_strategy = px.scatter(
        strategy_matrix,
        x='breadth_pct',
        y='avg_discount_depth',
        size='products_on_promo',
        color='promo_intensity_score',
        hover_data=['store_name', 'products_on_promo', 'aggressive_promos'],
        labels={
            'breadth_pct': 'Amplitude de Promoções (% do Catálogo)',
            'avg_discount_depth': 'Profundidade Média de Desconto (%)',
            'promo_intensity_score': 'Score de Intensidade',
            'products_on_promo': 'Produtos em Promoção'
        },
        title="Matriz Estratégica: Amplitude vs Profundidade de Promoções",
        color_continuous_scale='Viridis',
        text='store_name'
    )

    # Add quadrant lines
    avg_breadth = strategy_matrix['breadth_pct'].mean()
    avg_depth = strategy_matrix['avg_discount_depth'].mean()

    fig_strategy.add_hline(y=avg_depth, line_dash="dash", line_color="gray", opacity=0.5)
    fig_strategy.add_vline(x=avg_breadth, line_dash="dash", line_color="gray", opacity=0.5)

    # Add quadrant annotations
    fig_strategy.add_annotation(x=avg_breadth*1.5, y=avg_depth*1.5, text="Alto Impacto<br>(Alta Amplitude + Alta Profundidade)", showarrow=False, opacity=0.3)
    fig_strategy.add_annotation(x=avg_breadth*0.5, y=avg_depth*1.5, text="Descontos Seletivos<br>(Baixa Amplitude + Alta Profundidade)", showarrow=False, opacity=0.3)
    fig_strategy.add_annotation(x=avg_breadth*1.5, y=avg_depth*0.5, text="Promoções Rasas<br>(Alta Amplitude + Baixa Profundidade)", showarrow=False, opacity=0.3)
    fig_strategy.add_annotation(x=avg_breadth*0.5, y=avg_depth*0.5, text="Baixo Impacto<br>(Baixa Amplitude + Baixa Profundidade)", showarrow=False, opacity=0.3)

    fig_strategy.update_traces(textposition='top center', textfont_size=10)
    fig_strategy.update_layout(height=500, hovermode='closest')

    st.plotly_chart(fig_strategy, use_container_width=True)

    # Strategy insights
    top_intensity = strategy_matrix.nlargest(1, 'promo_intensity_score')
    if not top_intensity.empty:
        st.info(f"🏆 **Liderança em Intensidade Promocional**: {top_intensity.iloc[0]['store_name']} com score de {top_intensity.iloc[0]['promo_intensity_score']:.1f} ({top_intensity.iloc[0]['products_on_promo']} produtos, {top_intensity.iloc[0]['avg_discount_depth']:.1f}% desconto médio)")
else:
    st.warning("Sem dados de estratégia disponíveis para os filtros selecionados")

# Promotion Performance Over Time
st.markdown("---")
st.subheader("📈 Evolução Temporal de Promoções")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Volume de Promoções ao Longo do Tempo**")

    promo_evolution = conn.execute(f"""
    SELECT
        dd.date_day,
        ds.store_name,
        COUNT(DISTINCT ap.product_id) as products_on_promo,
        ROUND(AVG(ap.discount_percentage), 1) as avg_discount
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
        AND dd.date_day >= CURRENT_DATE - INTERVAL '30' DAY
    GROUP BY dd.date_day, ds.store_name
    ORDER BY dd.date_day, ds.store_name
    """).df()

    if not promo_evolution.empty:
        fig_evolution = px.line(
            promo_evolution,
            x='date_day',
            y='products_on_promo',
            color='store_name',
            markers=True,
            labels={'products_on_promo': 'Produtos em Promoção', 'date_day': 'Data', 'store_name': 'Loja'},
            hover_data=['avg_discount']
        )
        fig_evolution.update_layout(height=350, hovermode='x unified')
        st.plotly_chart(fig_evolution, use_container_width=True)
    else:
        st.info("Sem dados de evolução temporal")

with col2:
    st.markdown("**Evolução da Profundidade de Desconto**")

    discount_evolution = conn.execute(f"""
    SELECT
        dd.date_day,
        ds.store_name,
        ROUND(AVG(ap.discount_percentage), 1) as avg_discount,
        MAX(ap.discount_percentage) as max_discount
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
        AND dd.date_day >= CURRENT_DATE - INTERVAL '30' DAY
    GROUP BY dd.date_day, ds.store_name
    ORDER BY dd.date_day, ds.store_name
    """).df()

    if not discount_evolution.empty:
        fig_discount_evo = px.line(
            discount_evolution,
            x='date_day',
            y='avg_discount',
            color='store_name',
            markers=True,
            labels={'avg_discount': 'Desconto Médio (%)', 'date_day': 'Data', 'store_name': 'Loja'},
            hover_data=['max_discount']
        )
        fig_discount_evo.update_layout(height=350, hovermode='x unified')
        st.plotly_chart(fig_discount_evo, use_container_width=True)
    else:
        st.info("Sem dados de evolução de descontos")

# ROI Analysis: Best Value Promotions
st.markdown("---")
st.subheader("💎 Análise de Valor: Melhores Oportunidades de Economia")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("**Top 20 Produtos com Maior Economia Absoluta (R$)**")

    top_savings = conn.execute(f"""
    SELECT
        ap.product_name,
        ap.brand,
        ds.store_name,
        dr.city_name || ' - ' || dr.neighborhood_code as region,
        ROUND(ap.regular_price, 2) as regular_price,
        ROUND(ap.promotional_price, 2) as promo_price,
        ROUND(ap.regular_price - ap.promotional_price, 2) as absolute_savings,
        ROUND(ap.discount_percentage, 1) as discount_pct
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
    ORDER BY absolute_savings DESC
    LIMIT 20
    """).df()

    if not top_savings.empty:
        st.dataframe(
            top_savings.rename(columns={
                'product_name': 'Produto',
                'brand': 'Marca',
                'store_name': 'Loja',
                'region': 'Região',
                'regular_price': 'Preço Regular (R$)',
                'promo_price': 'Preço Promo (R$)',
                'absolute_savings': 'Economia (R$)',
                'discount_pct': 'Desconto (%)'
            }),
            use_container_width=True,
            height=400
        )
    else:
        st.info("Sem dados de economia disponíveis")

with col2:
    st.markdown("**Distribuição de Descontos**")

    discount_buckets = conn.execute(f"""
    SELECT
        CASE
            WHEN ap.discount_percentage < 10 THEN '0-10%'
            WHEN ap.discount_percentage < 20 THEN '10-20%'
            WHEN ap.discount_percentage < 30 THEN '20-30%'
            WHEN ap.discount_percentage < 40 THEN '30-40%'
            WHEN ap.discount_percentage < 50 THEN '40-50%'
            ELSE '50%+'
        END as discount_range,
        COUNT(*) as count
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
    GROUP BY discount_range
    ORDER BY
        CASE discount_range
            WHEN '0-10%' THEN 1
            WHEN '10-20%' THEN 2
            WHEN '20-30%' THEN 3
            WHEN '30-40%' THEN 4
            WHEN '40-50%' THEN 5
            ELSE 6
        END
    """).df()

    if not discount_buckets.empty:
        fig_buckets = px.pie(
            discount_buckets,
            names='discount_range',
            values='count',
            title="Produtos por Faixa de Desconto"
        )
        fig_buckets.update_traces(textposition='inside', textinfo='percent+label')
        fig_buckets.update_layout(height=400)
        st.plotly_chart(fig_buckets, use_container_width=True)
    else:
        st.info("Sem dados de distribuição")

# Hot Deals Section
st.markdown("---")
st.subheader("🔥 Hot Deals: Descontos Extremos (≥ 30%)")

# Get latest scrape date
latest_date_result = conn.execute("""
    SELECT MAX(dd.date_day) as latest
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
""").fetchone()
latest_date = latest_date_result[0] if latest_date_result and latest_date_result[0] else "N/A"

st.info(f"📅 **Última atualização:** {latest_date} | ✅ Dados válidos para hoje")

hot_deals = conn.execute(f"""
SELECT
    ap.product_id,
    ap.product_name,
    ap.brand,
    ds.store_name,
    dr.city_name || ' - ' || dr.neighborhood_code as region,
    ROUND(ap.promotional_price, 2) as promo_price,
    ROUND(ap.regular_price, 2) as regular_price,
    ROUND(ap.regular_price - ap.promotional_price, 2) as savings,
    ROUND(ap.discount_percentage, 1) as discount_pct,
    ap.promotion_type,
    dd.date_day as data_extracao
FROM dev_local.fct_active_promotions ap
JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
WHERE ap.discount_percentage >= 30
    AND ds.store_id IN ({stores_filter})
    AND dr.region_code IN ({regions_filter})
ORDER BY ap.discount_percentage DESC
LIMIT 100
""").df()

if not hot_deals.empty:
    st.dataframe(
        hot_deals.rename(columns={
            'product_id': 'ID',
            'product_name': 'Produto',
            'brand': 'Marca',
            'store_name': 'Loja',
            'region': 'Região',
            'promo_price': 'Preço Promo (R$)',
            'regular_price': 'Preço Regular (R$)',
            'savings': 'Economia (R$)',
            'discount_pct': 'Desconto (%)',
            'promotion_type': 'Tipo',
            'data_extracao': 'Data'
        }),
        use_container_width=True,
        height=400
    )

    # Download button
    st.download_button(
        label="⬇️ Baixar Hot Deals (CSV)",
        data=hot_deals.to_csv(index=False).encode('utf-8'),
        file_name=f"hot_deals_{latest_date}.csv",
        mime="text/csv"
    )
else:
    st.info("🔍 Nenhum hot deal disponível com os filtros selecionados")

# Category Analysis
st.markdown("---")
st.subheader("🏆 Top Marcas em Promoção")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Marcas com Mais Produtos Promocionados**")

    top_brands_volume = conn.execute(f"""
    SELECT
        brand,
        COUNT(DISTINCT product_id) as products_on_promo,
        ROUND(AVG(discount_percentage), 1) as avg_discount
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE brand IS NOT NULL
        AND ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
    GROUP BY brand
    ORDER BY products_on_promo DESC
    LIMIT 15
    """).df()

    if not top_brands_volume.empty:
        fig_brands_vol = px.bar(
            top_brands_volume,
            x='brand',
            y='products_on_promo',
            color='avg_discount',
            labels={'products_on_promo': 'Produtos em Promoção', 'brand': 'Marca', 'avg_discount': 'Desconto Médio (%)'},
            text='products_on_promo',
            color_continuous_scale='Reds'
        )
        fig_brands_vol.update_layout(xaxis_tickangle=-45, height=350)
        st.plotly_chart(fig_brands_vol, use_container_width=True)
    else:
        st.info("Sem dados de marcas")

with col2:
    st.markdown("**Marcas com Maiores Descontos Médios**")

    top_brands_discount = conn.execute(f"""
    SELECT
        brand,
        COUNT(DISTINCT product_id) as products_on_promo,
        ROUND(AVG(discount_percentage), 1) as avg_discount
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    WHERE brand IS NOT NULL
        AND ds.store_id IN ({stores_filter})
        AND dr.region_code IN ({regions_filter})
        AND ap.discount_percentage >= {min_discount}
    GROUP BY brand
    HAVING COUNT(DISTINCT product_id) >= 3
    ORDER BY avg_discount DESC
    LIMIT 15
    """).df()

    if not top_brands_discount.empty:
        fig_brands_disc = px.bar(
            top_brands_discount,
            x='brand',
            y='avg_discount',
            color='products_on_promo',
            labels={'avg_discount': 'Desconto Médio (%)', 'brand': 'Marca', 'products_on_promo': 'Produtos'},
            text='avg_discount',
            color_continuous_scale='Greens'
        )
        fig_brands_disc.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_brands_disc.update_layout(xaxis_tickangle=-45, height=350)
        st.plotly_chart(fig_brands_disc, use_container_width=True)
    else:
        st.info("Sem dados de marcas")

st.markdown("---")
st.caption("""
💡 **Insights Estratégicos**:
- **Amplitude vs Profundidade**: Lojas no quadrante superior direito têm estratégia agressiva (muitos produtos com bons descontos)
- **ROI**: Economia Potencial Total mostra quanto você pode economizar comprando tudo em promoção
- **Hot Deals**: Produtos com ≥30% de desconto representam oportunidades reais de economia
- **Tendências**: Acompanhe se lojas aumentam ou diminuem volume/profundidade ao longo do tempo
""")
