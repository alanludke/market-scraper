"""
Date Range Filter for Streamlit Dashboard
Provides consistent date filtering across all pages
"""

import streamlit as st
from datetime import datetime, timedelta, date
from typing import Tuple


def render_date_filter() -> Tuple[date, date]:
    """
    Render date range filter in sidebar.

    Returns:
        Tuple[date, date]: (start_date, end_date) selected by user
    """
    st.sidebar.header("📅 Período de Análise")

    # Predefined period options
    period_options = {
        "Últimos 7 dias": 7,
        "Últimos 14 dias": 14,
        "Últimos 30 dias": 30,
        "Todo o período (Jan 25 - Hoje)": None,  # Show all historical data
        "Customizado": -1
    }

    period_option = st.sidebar.selectbox(
        "Selecione o período",
        list(period_options.keys()),
        index=0  # Default to last 7 days
    )

    today = datetime.now().date()
    days = period_options[period_option]

    if days is None:
        # Show all historical data (from Jan 25, 2026)
        start_date = date(2026, 1, 25)
        end_date = today
        st.sidebar.info(f"📊 Incluindo dados históricos: {(today - start_date).days} dias")

    elif days == -1:
        # Custom date range
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Data Inicial",
                value=today - timedelta(days=7),
                min_value=date(2026, 1, 25),  # Earliest migrated data
                max_value=today
            )
        with col2:
            end_date = st.date_input(
                "Data Final",
                value=today,
                min_value=start_date,
                max_value=today
            )
    else:
        # Predefined period
        start_date = today - timedelta(days=days)
        end_date = today

    # Display selected range
    if period_option != "Customizado":
        days_diff = (end_date - start_date).days
        st.sidebar.caption(f"📅 {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')} ({days_diff} dias)")

    return start_date, end_date


def get_date_filter_sql(start_date: date, end_date: date, date_column: str = "scraped_date") -> str:
    """
    Generate SQL WHERE clause for date filtering.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        date_column: Name of the date column to filter on

    Returns:
        str: SQL WHERE clause (without 'WHERE' keyword)

    Example:
        >>> get_date_filter_sql(date(2026, 1, 25), date(2026, 2, 8))
        "scraped_date BETWEEN '2026-01-25' AND '2026-02-08'"
    """
    return f"{date_column} BETWEEN '{start_date}' AND '{end_date}'"


def show_data_coverage_warning(conn, start_date: date, end_date: date):
    """
    Show warning if no data available for selected period.

    Args:
        conn: DuckDB connection
        start_date: Start date
        end_date: End date
    """
    try:
        count = conn.execute(f"""
            SELECT COUNT(*) FROM dev_local.tru_product
            WHERE {get_date_filter_sql(start_date, end_date)}
        """).fetchone()[0]

        if count == 0:
            st.warning(f"""
            ⚠️ **Nenhum dado disponível para o período selecionado**

            - Período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}
            - Tente selecionar um período diferente
            """)
            return False

        return True

    except Exception as e:
        st.error(f"Erro ao verificar cobertura de dados: {e}")
        return False
