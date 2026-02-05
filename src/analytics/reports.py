"""Excel report generation for market intelligence."""

import logging
import pandas as pd
from datetime import datetime
from .engine import MarketAnalytics

logger = logging.getLogger("market_scraper")


def generate_reports(output_dir: str = "."):
    logger.info("Starting Market Intelligence Report...")
    db = MarketAnalytics()
    db.build_snapshot(days=7)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    excel_file = f"{output_dir}/Relatorio_Market_Intelligence_{timestamp}.xlsx"

    queries = {
        "1_Scorecard": """
            SELECT
                supermarket,
                COUNT(DISTINCT ean) as mix_produtos,
                ROUND(AVG(price), 2) as ticket_medio,
                COUNT(DISTINCT region) as lojas_monitoradas,
                MAX(collected_at) as ultima_atualizacao
            FROM snapshot
            GROUP BY supermarket
            ORDER BY mix_produtos DESC
        """,
        "2_Indice_Competitividade": """
            WITH comuns AS (
                SELECT ean FROM snapshot
                GROUP BY ean HAVING COUNT(DISTINCT supermarket) >= 2
            )
            SELECT
                t.supermarket,
                COUNT(DISTINCT t.ean) as itens_comparaveis,
                ROUND(SUM(t.price), 2) as custo_cesta,
                ROUND((SUM(t.price) / MIN(SUM(t.price)) OVER ()) * 100, 1) as indice_preco
            FROM snapshot t
            JOIN comuns c ON t.ean = c.ean
            GROUP BY t.supermarket
            ORDER BY indice_preco ASC
        """,
        "3_Ofertas_Recentes": """
            WITH historico AS (
                SELECT supermarket, ean, price as preco_antigo
                FROM silver_products
                WHERE collected_at BETWEEN CURRENT_DATE - INTERVAL 7 DAY
                                       AND CURRENT_DATE - INTERVAL 3 DAY
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY supermarket, ean ORDER BY collected_at DESC
                ) = 1
            )
            SELECT
                curr.supermarket,
                curr.name as produto,
                hist.preco_antigo as de,
                curr.price as por,
                ROUND(((hist.preco_antigo - curr.price) / hist.preco_antigo) * 100, 1)
                    as desconto_pct
            FROM snapshot curr
            JOIN historico hist
              ON curr.supermarket = hist.supermarket
             AND curr.ean = REGEXP_REPLACE(TRIM(COALESCE(hist.ean, '')), '^0+', '')
            WHERE curr.price < hist.preco_antigo
              AND ((hist.preco_antigo - curr.price) / hist.preco_antigo) >= 0.10
            ORDER BY desconto_pct DESC
            LIMIT 100
        """,
        "4_Gaps_Arbitragem": """
            SELECT
                ean,
                MIN(name) as produto,
                arg_min(supermarket, price) as loja_barata,
                MIN(price) as preco_min,
                arg_max(supermarket, price) as loja_cara,
                MAX(price) as preco_max,
                ROUND(((MAX(price) - MIN(price)) / MIN(price)) * 100, 1) as gap_pct
            FROM snapshot
            GROUP BY ean
            HAVING COUNT(DISTINCT supermarket) >= 2 AND gap_pct > 30
            ORDER BY gap_pct DESC
            LIMIT 10000
        """,
        "5_Posicionamento_Preco": """
            SELECT
                supermarket,
                COUNT(CASE WHEN price <= 10 THEN 1 END) as ate_10,
                COUNT(CASE WHEN price > 10 AND price <= 30 THEN 1 END) as de_10_a_30,
                COUNT(CASE WHEN price > 30 THEN 1 END) as acima_30,
                ROUND(AVG(price), 2) as preco_medio
            FROM snapshot
            GROUP BY supermarket
        """,
        "6_Auditoria_Volume": """
            SELECT
                supermarket,
                CAST(collected_at AS DATE) as dia,
                region,
                COUNT(*) as volume
            FROM silver_products
            WHERE collected_at >= CURRENT_DATE - INTERVAL 7 DAY
            GROUP BY supermarket, dia, region
            ORDER BY dia DESC, volume DESC
        """,
    }

    with pd.ExcelWriter(excel_file, engine="xlsxwriter") as writer:
        for sheet_name, sql in queries.items():
            try:
                df = db.query(sql)
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    logger.info(f"  {sheet_name}: {len(df)} rows")
                else:
                    logger.info(f"  {sheet_name}: empty")
            except Exception as e:
                logger.error(f"  {sheet_name}: {e}")

    logger.info(f"Report saved: {excel_file}")
    return excel_file
