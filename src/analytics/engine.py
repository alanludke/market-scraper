"""
DuckDB analytics engine for market data.

=== GUIA DE USO DO DUCKDB ===

O DuckDB e um banco OLAP (colunar, otimizado para leitura e agregacao).
Ele le JSONL direto do disco sem precisar importar antes.

CONCEITOS IMPORTANTES:

1. VIEW vs TABLE:
   - VIEW: nao armazena dados, re-le os arquivos a cada query. Bom para dados
     que mudam frequentemente (novas coletas). E o que usamos para silver_products.
   - TABLE: armazena os dados no .duckdb file. Mais rapido para queries repetidas,
     mas precisa ser recriado quando novos dados chegam.

2. OTIMIZACAO DE QUERIES:
   - DuckDB faz scan colunar: SELECT so as colunas que precisa (evite SELECT *)
   - Filtros WHERE sao pushdown: filtrar por supermarket/region e barato
   - GROUP BY e muito rapido (hash aggregation nativo)
   - Para queries sobre o snapshot mais recente, use a temp table 'snapshot'

3. EXEMPLOS UTEIS:

   -- Preco medio por supermercado (snapshot mais recente)
   SELECT supermarket, ROUND(AVG(price), 2) as avg_price
   FROM snapshot GROUP BY supermarket;

   -- Produtos em comum entre lojas
   SELECT ean, COUNT(DISTINCT supermarket) as n_stores, MIN(price), MAX(price)
   FROM snapshot WHERE ean != ''
   GROUP BY ean HAVING n_stores >= 2
   ORDER BY (MAX(price) - MIN(price)) DESC LIMIT 20;

   -- Historico de preco de um produto especifico
   SELECT supermarket, region, price, collected_at
   FROM silver_products WHERE ean = '7891000100103'
   ORDER BY collected_at;

   -- Volume coletado por dia
   SELECT CAST(collected_at AS DATE) as dia, supermarket, COUNT(*) as n
   FROM silver_products GROUP BY dia, supermarket ORDER BY dia DESC;

4. PERFORMANCE:
   - Primeira query e mais lenta (DuckDB precisa parsear os JSONLs)
   - Queries subsequentes sao rapidas (cache interno)
   - Se ficar lento (>100GB), considere converter para Parquet:
     COPY (SELECT * FROM silver_products) TO 'data/silver.parquet' (FORMAT PARQUET);
   - Depois leia do Parquet (10-50x mais rapido que JSONL):
     SELECT * FROM 'data/silver.parquet' WHERE supermarket = 'bistek';
"""

import os
import glob
import logging
import duckdb

logger = logging.getLogger("market_scraper")


class MarketAnalytics:
    def __init__(self, db_path: str = "market_data.duckdb"):
        self.con = duckdb.connect(db_path, config={
            "temp_directory": "duckdb_tmp",
            "memory_limit": "4GB",
        })
        self._init_silver_view()

    def _find_jsonl_files(self) -> list[str]:
        """Find all consolidated JSONL files across old and new directory structures."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(base_dir))

        patterns = [
            # New structure: data/bronze/**/*_full.jsonl
            os.path.join(project_root, "data", "bronze", "**", "*_full.jsonl"),
            # Old structure: *_products_scraper/data/bronze/**/*_full.jsonl
            os.path.join(project_root, "*_products_scraper", "data", "bronze", "**", "*_full.jsonl"),
            os.path.join(project_root, "bad_*_products_scraper", "data", "bronze", "**", "*_full.jsonl"),
        ]

        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern, recursive=True))

        if not files:
            # Fallback: try microbatches
            for pattern in patterns:
                fallback = pattern.replace("*_full.jsonl", "*.jsonl")
                files.extend(glob.glob(fallback, recursive=True))

        # Normalize to forward slashes (DuckDB preference)
        return [f.replace(os.sep, "/") for f in files]

    def _init_silver_view(self):
        """Create the silver_products view that reads from all bronze JSONL files."""
        files = self._find_jsonl_files()
        if not files:
            logger.warning("No JSONL files found. Analytics will be empty.")
            self.con.execute("CREATE OR REPLACE VIEW silver_products AS SELECT 1 WHERE false")
            return

        logger.info(f"Found {len(files)} JSONL files for analytics")
        file_list_sql = ", ".join(f"'{f}'" for f in files)

        view_query = f"""
        CREATE OR REPLACE VIEW silver_products AS
        WITH raw AS (
            SELECT
                TRY_CAST(_metadata.scraped_at AS TIMESTAMP) as collected_at,
                _metadata.region as region,
                COALESCE(
                    _metadata.supermarket,
                    regexp_extract(filename, 'supermarket=([^/\\\\]+)', 1),
                    'unknown'
                ) as supermarket,
                productId as sku,
                productName as name,
                brand,
                COALESCE(items[1].ean, items[1].referenceId[1].Value) as ean_raw,
                TRY_CAST(items[1].sellers[1].commertialOffer.Price AS DOUBLE) as price,
                TRY_CAST(items[1].sellers[1].commertialOffer.ListPrice AS DOUBLE) as list_price,
                TRY_CAST(items[1].sellers[1].commertialOffer.AvailableQuantity AS INT) as stock,
                categories[1] as category_path,
                items[1].images[1].imageUrl as image_url,
                filename
            FROM read_json_auto([{file_list_sql}], union_by_name=true, filename=true)
        )
        SELECT
            collected_at, region, supermarket, sku, name, brand,
            REGEXP_REPLACE(TRIM(COALESCE(ean_raw, '')), '^0+', '') as ean,
            price, list_price, stock, category_path, image_url
        FROM raw
        WHERE price > 0
        """

        try:
            self.con.execute(view_query)
        except duckdb.CatalogException:
            self.con.execute("DROP TABLE IF EXISTS silver_products")
            self.con.execute(view_query)

        logger.info("silver_products view ready")

    def build_snapshot(self, days: int = 7):
        """
        Create a temp table with the most recent valid collection per store/region.
        This is the 'photo' used for cross-store comparisons.
        """
        self.con.execute(f"""
        CREATE OR REPLACE TEMP TABLE snapshot AS
        WITH latest_runs AS (
            SELECT supermarket, region, MAX(collected_at) as ts
            FROM (
                SELECT supermarket, region, collected_at, COUNT(*) as vol
                FROM silver_products
                WHERE collected_at >= CURRENT_DATE - INTERVAL {days} DAY
                GROUP BY supermarket, region, collected_at
            )
            GROUP BY supermarket, region
        )
        SELECT
            t.supermarket, t.region, t.sku, t.name, t.brand,
            t.price, t.list_price, t.stock, t.category_path,
            t.collected_at,
            REGEXP_REPLACE(TRIM(COALESCE(t.ean, '')), '^0+', '') as ean
        FROM silver_products t
        JOIN latest_runs lr
          ON t.supermarket = lr.supermarket
         AND t.region = lr.region
         AND t.collected_at = lr.ts
        WHERE t.price > 0
          AND t.ean IS NOT NULL
          AND t.ean != ''
        """)
        logger.info("Snapshot table ready")

    def query(self, sql: str):
        """Run arbitrary SQL and return a pandas DataFrame."""
        return self.con.execute(sql).df()

    def stats(self):
        """Quick overview of data volume."""
        return self.query("""
            SELECT
                supermarket,
                COUNT(DISTINCT region) as regions,
                COUNT(DISTINCT sku) as products,
                ROUND(AVG(price), 2) as avg_price,
                MIN(collected_at) as first_collection,
                MAX(collected_at) as last_collection
            FROM silver_products
            GROUP BY supermarket
            ORDER BY products DESC
        """)

    def convert_to_parquet(self, output_path: str = "data/silver_products.parquet"):
        """
        Convert silver view to Parquet for 10-50x faster queries.
        Run this periodically (e.g., after each collection cycle).

        After conversion, query directly:
            SELECT * FROM 'data/silver_products.parquet' WHERE supermarket='bistek'
        """
        self.con.execute(f"""
            COPY (SELECT * FROM silver_products)
            TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        logger.info(f"Exported silver layer to {output_path}")
