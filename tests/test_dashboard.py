"""
Testes automatizados para Dashboard Streamlit.

Valida:
- Conexão com DuckDB
- Queries SQL corretas
- Dados retornados corretamente
- Performance de queries

Usage:
    pytest tests/test_dashboard.py -v
"""

import pytest
import duckdb
from pathlib import Path
import pandas as pd


@pytest.fixture
def db_connection():
    """Fixture para conexão DuckDB."""
    db_path = Path(__file__).parent.parent / "data" / "analytics.duckdb"
    if not db_path.exists():
        pytest.skip(f"Database not found: {db_path}")

    conn = duckdb.connect(str(db_path), read_only=True)
    yield conn
    conn.close()


class TestDatabaseConnection:
    """Testes de conexão e validação de schema."""

    def test_database_exists(self, db_connection):
        """Verifica se o banco de dados existe e está acessível."""
        assert db_connection is not None

    def test_required_tables_exist(self, db_connection):
        """Verifica se todas as tabelas necessárias existem."""
        required_tables = [
            'tru_product',
            'dim_date',
            'dim_store',
            'dim_region',
            'dim_brand',
            'dim_product',
            'fct_daily_prices',
            'fct_active_promotions',
            'fct_price_comparison_v2'
        ]

        tables = db_connection.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'dev_local'
        """).df()['table_name'].tolist()

        for table in required_tables:
            assert table in tables, f"Required table {table} not found"

    def test_dim_store_schema(self, db_connection):
        """Valida schema da dim_store (corrigir erros de coluna)."""
        columns = db_connection.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'dev_local'
              AND table_name = 'dim_store'
        """).df()['column_name'].tolist()

        # Verificar colunas corretas
        assert 'store_key' in columns
        assert 'store_id' in columns  # NOT supermarket
        assert 'store_name' in columns


class TestDashboardQueries:
    """Testes das queries usadas nos dashboards."""

    def test_price_analysis_query(self, db_connection):
        """Testa query da página de Análise de Preços."""
        query = """
        SELECT
            ds.store_name as supermarket,
            dp.min_price
        FROM dev_local.fct_daily_prices dp
        JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
        WHERE ds.store_id IN ('bistek', 'fort', 'giassi')
            AND dp.min_price BETWEEN 1 AND 500
        LIMIT 100
        """

        result = db_connection.execute(query).df()

        assert len(result) > 0, "Query returned no results"
        assert 'supermarket' in result.columns
        assert 'min_price' in result.columns
        assert result['min_price'].min() >= 1
        assert result['min_price'].max() <= 500

    def test_promotions_query(self, db_connection):
        """Testa query da página de Promoções."""
        query = """
        SELECT
            ap.product_name,
            ds.store_name as supermarket,
            round(ap.promotional_price, 2) as promo_price,
            round(ap.discount_percentage, 1) as discount_pct
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE ap.discount_percentage >= 30
        LIMIT 50
        """

        result = db_connection.execute(query).df()

        # Pode não ter hot deals, mas query deve funcionar
        assert 'product_name' in result.columns
        assert 'discount_pct' in result.columns

        if len(result) > 0:
            assert result['discount_pct'].min() >= 30

    def test_competitiveness_query(self, db_connection):
        """Testa query da página de Competitividade."""
        query = """
        SELECT
            product_id,
            product_name,
            count(DISTINCT store_key) as store_count,
            min(min_price) as lowest_price,
            max(min_price) as highest_price
        FROM dev_local.fct_price_comparison_v2
        GROUP BY product_id, product_name
        HAVING count(DISTINCT store_key) >= 2
        LIMIT 50
        """

        result = db_connection.execute(query).df()

        if len(result) > 0:
            assert result['store_count'].min() >= 2
            assert (result['highest_price'] >= result['lowest_price']).all()


class TestDataQuality:
    """Testes de qualidade de dados."""

    def test_no_null_prices(self, db_connection):
        """Verifica se não há preços nulos em fct_daily_prices."""
        null_count = db_connection.execute("""
            SELECT count(*)
            FROM dev_local.fct_daily_prices
            WHERE min_price IS NULL
        """).fetchone()[0]

        assert null_count == 0, f"Found {null_count} null prices"

    def test_discount_percentage_valid(self, db_connection):
        """Verifica se percentual de desconto está no range válido."""
        invalid_count = db_connection.execute("""
            SELECT count(*)
            FROM dev_local.fct_active_promotions
            WHERE discount_percentage < 0 OR discount_percentage > 100
        """).fetchone()[0]

        assert invalid_count == 0, f"Found {invalid_count} invalid discount percentages"

    def test_referential_integrity_stores(self, db_connection):
        """Testa integridade referencial store_key."""
        orphan_count = db_connection.execute("""
            SELECT count(*)
            FROM dev_local.fct_daily_prices dp
            LEFT JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
            WHERE ds.store_key IS NULL
        """).fetchone()[0]

        assert orphan_count == 0, f"Found {orphan_count} orphaned store_keys"


class TestPerformance:
    """Testes de performance de queries."""

    def test_price_index_query_performance(self, db_connection):
        """Verifica performance da query de índice de preços."""
        import time

        start = time.time()
        result = db_connection.execute("""
            SELECT
                ds.store_name,
                round(avg(dp.min_price), 2) as avg_price,
                count(DISTINCT dp.product_key) as product_count
            FROM dev_local.fct_daily_prices dp
            JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
            GROUP BY ds.store_name
        """).df()
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Query took {elapsed:.2f}s (>5s threshold)"
        assert len(result) > 0

    def test_hot_deals_query_performance(self, db_connection):
        """Verifica performance da query de hot deals."""
        import time

        start = time.time()
        result = db_connection.execute("""
            SELECT *
            FROM dev_local.fct_active_promotions
            WHERE discount_percentage >= 30
            ORDER BY discount_percentage DESC
            LIMIT 50
        """).df()
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Query took {elapsed:.2f}s (>3s threshold)"


# Testes de integração
class TestDashboardIntegration:
    """Testes de integração end-to-end."""

    def test_complete_price_analysis_workflow(self, db_connection):
        """Simula workflow completo da página de preços."""
        # 1. Carregar lojas
        stores = db_connection.execute("""
            SELECT DISTINCT store_id, store_name
            FROM dev_local.dim_store
            ORDER BY store_name
        """).df()

        assert len(stores) > 0

        # 2. Filtrar dados por loja
        selected_stores = stores['store_id'].tolist()

        # 3. Carregar distribuição de preços
        price_dist = db_connection.execute(f"""
            SELECT ds.store_name, dp.min_price
            FROM dev_local.fct_daily_prices dp
            JOIN dev_local.dim_store ds ON dp.store_key = ds.store_key
            WHERE ds.store_id IN ({','.join([f"'{s}'" for s in selected_stores])})
                AND dp.min_price BETWEEN 1 AND 500
            LIMIT 1000
        """).df()

        assert len(price_dist) > 0

        # 4. Calcular estatísticas
        stats = price_dist.groupby('store_name')['min_price'].agg(['mean', 'min', 'max'])

        assert len(stats) > 0
        assert (stats['max'] >= stats['min']).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
