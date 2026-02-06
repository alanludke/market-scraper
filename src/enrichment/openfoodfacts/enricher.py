"""
OpenFoodFacts EAN enrichment pipeline.

Fetches product data from OpenFoodFacts API based on EAN codes extracted
from VTEX products, enabling nutritional analysis and product deduplication.
"""

import requests
import duckdb
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

from src.schemas.openfoodfacts import OpenFoodFactsProduct
from src.ingest.scrapers.rate_limiter import RateLimiter
from src.ingest.loaders.parquet_writer import write_parquet


class EANEnrichmentPipeline:
    """
    Enrich EANs from VTEX products using OpenFoodFacts API.

    This pipeline:
    1. Extracts unique EANs from tru_product (trusted layer)
    2. Fetches product data from OpenFoodFacts API with rate limiting
    3. Validates responses with Pydantic schema
    4. Saves enriched data to bronze layer (Parquet)

    Example:
        pipeline = EANEnrichmentPipeline()
        eans = pipeline.extract_unique_eans()
        products = pipeline.fetch_ean_batch(eans[:100])
        pipeline.save_to_bronze(products, run_id="test_run")
    """

    BASE_URL = "https://world.openfoodfacts.org/api/v0"

    def __init__(self, db_path: str = "data/analytics.duckdb"):
        """
        Initialize enrichment pipeline.

        Args:
            db_path: Path to DuckDB database with tru_product table
        """
        self.db_path = db_path
        # 10 req/s for OpenFoodFacts (600 req/min)
        # Separate rate limiter from VTEX scrapers
        self.rate_limiter = RateLimiter(
            rate_limit=600,
            window_seconds=60,
            max_concurrent=1  # Sequential requests for simplicity
        )

        # Statistics
        self.stats = {
            "eans_extracted": 0,
            "eans_fetched": 0,
            "products_found": 0,
            "products_not_found": 0,
            "validation_errors": 0,
            "api_errors": 0
        }

    def extract_unique_eans(self) -> List[str]:
        """
        Extract all unique EANs from tru_product.

        Queries the trusted layer to get all distinct EAN codes from
        VTEX products. Filters for valid EAN lengths (8, 13, 14).

        Returns:
            List of unique EAN codes sorted alphabetically
        """
        query = """
            WITH unnested_eans AS (
                SELECT DISTINCT unnest(eans) as ean
                FROM dev_local.tru_product
                WHERE eans IS NOT NULL
                    AND len(eans) > 0
            )
            SELECT ean
            FROM unnested_eans
            WHERE length(ean) IN (8, 13, 14)
            ORDER BY ean
        """

        logger.info("Extracting unique EANs from tru_product")

        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            result = conn.execute(query).fetchdf()
            conn.close()

            eans = result['ean'].tolist()
            self.stats["eans_extracted"] = len(eans)

            logger.info(f"Extracted {len(eans)} unique EANs")
            return eans

        except Exception as e:
            logger.error(f"Failed to extract EANs from database: {e}")
            raise

    def fetch_ean_batch(self, eans: List[str]) -> List[Dict]:
        """
        Fetch EAN data from OpenFoodFacts API with rate limiting.

        Makes sequential API calls with rate limiting (10 req/s).
        Validates responses with Pydantic schema.
        Handles 404s gracefully (EAN not found in database).

        Args:
            eans: List of EAN codes to fetch

        Returns:
            List of product dictionaries (validated by Pydantic)
        """
        products = []
        total = len(eans)

        logger.info(f"Fetching {total} EANs from OpenFoodFacts API")

        for idx, ean in enumerate(eans, 1):
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{total} EANs ({idx/total*100:.1f}%)")

            with self.rate_limiter.limit():
                url = f"{self.BASE_URL}/product/{ean}.json"

                try:
                    response = requests.get(url, timeout=10)
                    self.stats["eans_fetched"] += 1

                    if response.status_code == 200:
                        data = response.json()

                        if data.get('status') == 1:  # Product found
                            try:
                                # Validate with Pydantic schema
                                product = OpenFoodFactsProduct.model_validate(data['product'])
                                products.append(product.model_dump())
                                self.stats["products_found"] += 1

                            except Exception as e:
                                logger.warning(f"Validation failed for EAN {ean}: {e}")
                                self.stats["validation_errors"] += 1
                        else:
                            # Status 0 = Product not found in database
                            logger.debug(f"EAN {ean} not found in OpenFoodFacts")
                            self.stats["products_not_found"] += 1

                    elif response.status_code == 404:
                        logger.debug(f"EAN {ean} returned 404")
                        self.stats["products_not_found"] += 1

                    else:
                        logger.error(f"API error for EAN {ean}: HTTP {response.status_code}")
                        self.stats["api_errors"] += 1

                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout for EAN {ean}")
                    self.stats["api_errors"] += 1

                except Exception as e:
                    logger.error(f"Unexpected error for EAN {ean}: {e}")
                    self.stats["api_errors"] += 1

        logger.info(f"Fetching complete: {len(products)} products found")
        return products

    def save_to_bronze(self, products: List[Dict], run_id: str) -> str:
        """
        Save enriched products to bronze layer.

        Saves products as Parquet file with Hive partitioning:
        data/bronze/supermarket=openfoodfacts/region=global/year=YYYY/month=MM/day=DD/

        Args:
            products: List of product dictionaries
            run_id: Unique run identifier

        Returns:
            Path to saved Parquet file
        """
        now = datetime.now()

        output_path = Path(
            f"data/bronze/supermarket=openfoodfacts/region=global/"
            f"year={now.year}/month={now.month:02d}/day={now.day:02d}/"
            f"run_{run_id}.parquet"
        )

        metadata = {
            "run_id": run_id,
            "supermarket": "openfoodfacts",
            "region": "global",
            "scraped_at": now.isoformat()
        }

        logger.info(f"Saving {len(products)} products to {output_path}")

        record_count = write_parquet(
            items=products,
            output_path=output_path,  # Pass Path object, not string
            metadata=metadata,
            compression="snappy"
        )

        logger.info(f"Saved {record_count} products successfully")
        return str(output_path)

    def get_stats(self) -> Dict:
        """
        Get enrichment statistics.

        Returns:
            Dictionary with enrichment stats (EANs extracted, products found, errors, etc.)
        """
        return {
            **self.stats,
            "success_rate": (
                self.stats["products_found"] / self.stats["eans_fetched"] * 100
                if self.stats["eans_fetched"] > 0 else 0
            )
        }

    def run_full_enrichment(self, run_id: str, limit: int = None) -> Dict:
        """
        Run full enrichment pipeline (extract → fetch → save).

        Args:
            run_id: Unique run identifier
            limit: Optional limit on number of EANs to fetch (for testing)

        Returns:
            Dictionary with run statistics
        """
        logger.info(f"Starting full EAN enrichment (run_id={run_id})")

        # Extract EANs
        eans = self.extract_unique_eans()

        # Apply limit if specified
        if limit:
            eans = eans[:limit]
            logger.info(f"Limited to {limit} EANs for testing")

        # Fetch from API
        products = self.fetch_ean_batch(eans)

        # Save to bronze
        if products:
            output_path = self.save_to_bronze(products, run_id)
        else:
            logger.warning("No products found, skipping save")
            output_path = None

        # Return stats
        stats = self.get_stats()
        stats["output_path"] = output_path

        logger.info(f"Enrichment complete: {stats}")
        return stats
