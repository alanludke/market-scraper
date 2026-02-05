"""Streamlit dashboard for market intelligence."""

import streamlit as st
from src.analytics.engine import MarketAnalytics

st.set_page_config(page_title="Market Intelligence", layout="wide")
st.title("Market Scraper Dashboard")


@st.cache_resource
def get_db():
    db = MarketAnalytics()
    db.build_snapshot(days=7)
    return db


try:
    db = get_db()
except Exception as e:
    st.error(f"Failed to initialize database: {e}")
    st.stop()

# Overview
st.subheader("Overview")
stats = db.stats()
if not stats.empty:
    st.dataframe(stats, use_container_width=True)

st.divider()

# Price search
st.subheader("Price Search")
search = st.text_input("Product name or EAN", placeholder="e.g. leite, arroz, 7891000100103")

if search:
    results = db.query(f"""
        SELECT supermarket, region, name, ean, price, collected_at
        FROM snapshot
        WHERE name ILIKE '%{search}%' OR ean LIKE '%{search}%'
        ORDER BY price ASC
        LIMIT 100
    """)
    if not results.empty:
        st.write(f"Found {len(results)} items")
        st.dataframe(
            results,
            column_config={"price": st.column_config.NumberColumn(format="R$ %.2f")},
            use_container_width=True,
        )
    else:
        st.info("No matches found.")

st.divider()

# Custom SQL
st.subheader("Custom Query")
sql = st.text_area(
    "DuckDB SQL",
    value="SELECT supermarket, COUNT(DISTINCT ean) as products FROM snapshot GROUP BY supermarket",
    height=100,
)
if st.button("Run"):
    try:
        df = db.query(sql)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(str(e))
