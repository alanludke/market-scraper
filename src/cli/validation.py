"""
CLI para validar hot deals.

Valida se os hot deals ainda estão ativos fazendo scraping das páginas.

Usage:
    # Validar todos os hot deals
    python cli_validate_deals.py --all

    # Validar apenas top 50
    python cli_validate_deals.py --limit 50

    # Validar e salvar resultados
    python cli_validate_deals.py --all --output data/validation_results.csv
"""

import click
import duckdb
import pandas as pd
from pathlib import Path
from loguru import logger
from src.analytics.hot_deal_validator import validate_hot_deals_sync
from datetime import datetime


@click.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Número máximo de deals para validar (default: todos)",
)
@click.option(
    "--min-discount",
    "-d",
    type=float,
    default=30.0,
    help="Desconto mínimo para considerar hot deal (default: 30%)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Arquivo de saída para resultados (CSV)",
)
@click.option(
    "--store",
    "-s",
    type=str,
    default=None,
    help="Filtrar por loja específica (bistek, fort, giassi)",
)
@click.option(
    "--save-to-db",
    is_flag=True,
    help="Salvar resultados no DuckDB (tabela validation_results)",
)
def validate_deals(
    limit: int,
    min_discount: float,
    output: str,
    store: str,
    save_to_db: bool,
):
    """Valida hot deals fazendo scraping das páginas de produtos."""

    logger.info("🔍 Iniciando validação de hot deals...")

    # Conectar ao banco
    db_path = Path("data/analytics.duckdb")
    if not db_path.exists():
        logger.error(f"Banco de dados não encontrado: {db_path}")
        raise click.Abort()

    conn = duckdb.connect(str(db_path), read_only=not save_to_db)

    # Montar query
    query = f"""
    SELECT
        ap.product_id,
        ap.product_name,
        ap.brand,
        ds.store_id as supermarket,
        ds.store_name,
        dr.city_name || ' - ' || dr.neighborhood_code as region,
        round(ap.promotional_price, 2) as promo_price,
        round(ap.regular_price, 2) as regular_price,
        round(ap.discount_percentage, 1) as discount_pct,
        ap.promotion_type,
        dd.date_day as extraction_date,
        (SELECT product_url FROM dev_local.tru_product tp
         WHERE tp.product_id = ap.product_id
           AND tp.supermarket = ds.store_id
         LIMIT 1) as product_url
    FROM dev_local.fct_active_promotions ap
    JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
    JOIN dev_local.dim_region dr ON ap.region_key = dr.region_key
    JOIN dev_local.dim_date dd ON ap.date_key = dd.date_key
    WHERE ap.discount_percentage >= {min_discount}
    """

    if store:
        query += f" AND ds.store_id = '{store}'"

    query += " ORDER BY ap.discount_percentage DESC"

    if limit:
        query += f" LIMIT {limit}"

    hot_deals = conn.execute(query).df()

    if hot_deals.empty:
        logger.warning("Nenhum hot deal encontrado com os filtros especificados.")
        return

    logger.info(f"📊 Encontrados {len(hot_deals)} hot deals para validar")
    logger.info(f"   - Desconto mínimo: {min_discount}%")
    if store:
        logger.info(f"   - Loja: {store}")
    if limit:
        logger.info(f"   - Limite: {limit}")

    # Validar
    click.echo("\n🔎 Validando deals (fazendo scraping das páginas)...")
    validated = validate_hot_deals_sync(hot_deals)

    # Estatísticas
    total = len(validated)
    valid = validated["is_deal_valid"].sum()
    expired = (validated["validation_status"] == "expired").sum()
    errors = (validated["validation_status"] == "error").sum()
    no_url = (validated["validation_status"] == "no_url").sum()

    click.echo("\n" + "=" * 60)
    click.echo("📈 RESULTADOS DA VALIDAÇÃO")
    click.echo("=" * 60)
    click.echo(f"Total de deals validados:     {total}")
    click.echo(f"✅ Deals válidos (ativos):     {valid} ({valid/total*100:.1f}%)")
    click.echo(f"⏰ Deals expirados:            {expired} ({expired/total*100:.1f}%)")
    click.echo(f"❌ Erros na validação:         {errors} ({errors/total*100:.1f}%)")
    click.echo(f"🔗 Sem URL disponível:         {no_url} ({no_url/total*100:.1f}%)")
    click.echo("=" * 60)

    # Mostrar deals expirados
    if expired > 0:
        click.echo("\n⚠️  DEALS EXPIRADOS (não estão mais com o desconto anunciado):")
        expired_deals = validated[validated["validation_status"] == "expired"][
            [
                "product_name",
                "supermarket",
                "discount_pct",
                "current_discount_scraped",
                "promo_price",
                "current_price_scraped",
            ]
        ]
        click.echo(expired_deals.to_string(index=False))

    # Salvar resultados
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        validated.to_csv(output_path, index=False)
        logger.info(f"💾 Resultados salvos em: {output_path}")

    # Salvar no banco
    if save_to_db:
        conn_write = duckdb.connect(str(db_path), read_only=False)

        # Adicionar metadata
        validated["validation_run_at"] = datetime.now().isoformat()

        # Criar tabela se não existir
        conn_write.execute("""
            CREATE TABLE IF NOT EXISTS dev_local.hot_deal_validations (
                product_id VARCHAR,
                product_name VARCHAR,
                brand VARCHAR,
                supermarket VARCHAR,
                store_name VARCHAR,
                region VARCHAR,
                promo_price DOUBLE,
                regular_price DOUBLE,
                discount_pct DOUBLE,
                promotion_type VARCHAR,
                extraction_date DATE,
                product_url VARCHAR,
                validation_status VARCHAR,
                current_price_scraped DOUBLE,
                current_discount_scraped DOUBLE,
                is_deal_valid BOOLEAN,
                validation_error VARCHAR,
                validated_at TIMESTAMP,
                validation_run_at TIMESTAMP
            )
        """)

        # Inserir dados
        conn_write.execute(
            "INSERT INTO dev_local.hot_deal_validations SELECT * FROM validated"
        )
        conn_write.close()

        logger.info("💾 Resultados salvos no banco: dev_local.hot_deal_validations")

    click.echo("\n✅ Validação concluída!")


if __name__ == "__main__":
    validate_deals()
