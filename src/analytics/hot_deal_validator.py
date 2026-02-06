"""
Hot Deal Validator - Verifica se promoções ainda estão ativas.

Faz scraping das páginas de produto para confirmar que os hot deals
ainda estão com o desconto anunciado.

Usage:
    validator = HotDealValidator()
    results = await validator.validate_deals(hot_deals_df)
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
import re


class HotDealValidator:
    """Valida hot deals fazendo scraping das páginas de produtos."""

    def __init__(self, max_concurrent: int = 10, timeout: int = 15):
        """
        Args:
            max_concurrent: Máximo de requisições simultâneas
            timeout: Timeout em segundos para cada requisição
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def validate_deal(
        self,
        product_url: str,
        expected_price: float,
        expected_discount: float,
        store_id: str,
    ) -> Dict[str, Any]:
        """
        Valida um hot deal específico.

        Args:
            product_url: URL do produto
            expected_price: Preço promocional esperado
            expected_discount: Desconto percentual esperado
            store_id: ID da loja (bistek, fort, giassi)

        Returns:
            dict: {
                'is_valid': bool,
                'current_price': float | None,
                'current_discount': float | None,
                'status': str,  # 'active', 'expired', 'error', 'no_url'
                'error': str | None,
                'validated_at': str
            }
        """
        if not product_url or pd.isna(product_url):
            return {
                "is_valid": False,
                "current_price": None,
                "current_discount": None,
                "status": "no_url",
                "error": "URL não disponível",
                "validated_at": datetime.now().isoformat(),
            }

        async with self.semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        product_url, timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status != 200:
                            return {
                                "is_valid": False,
                                "current_price": None,
                                "current_discount": None,
                                "status": "error",
                                "error": f"HTTP {response.status}",
                                "validated_at": datetime.now().isoformat(),
                            }

                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        # Extrair dados do produto (VTEX armazena em JSON no HTML)
                        product_data = self._extract_vtex_product_data(soup)

                        if not product_data:
                            # Fallback: tentar parsear HTML diretamente
                            product_data = self._extract_from_html(soup, store_id)

                        if not product_data:
                            return {
                                "is_valid": False,
                                "current_price": None,
                                "current_discount": None,
                                "status": "error",
                                "error": "Não foi possível extrair dados do produto",
                                "validated_at": datetime.now().isoformat(),
                            }

                        current_price = product_data.get("price")
                        current_discount = product_data.get("discount_pct", 0)

                        # Validação com tolerância
                        price_tolerance = 0.05  # 5% de tolerância no preço
                        discount_tolerance = 0.10  # 10% de tolerância no desconto

                        is_price_valid = (
                            current_price is not None
                            and current_price <= expected_price * (1 + price_tolerance)
                        )
                        is_discount_valid = current_discount >= expected_discount * (
                            1 - discount_tolerance
                        )

                        is_valid = is_price_valid and is_discount_valid

                        return {
                            "is_valid": is_valid,
                            "current_price": current_price,
                            "current_discount": current_discount,
                            "status": "active" if is_valid else "expired",
                            "error": None,
                            "validated_at": datetime.now().isoformat(),
                        }

            except asyncio.TimeoutError:
                logger.warning(f"Timeout ao validar {product_url}")
                return {
                    "is_valid": False,
                    "current_price": None,
                    "current_discount": None,
                    "status": "error",
                    "error": "Timeout",
                    "validated_at": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Erro ao validar {product_url}: {e}")
                return {
                    "is_valid": False,
                    "current_price": None,
                    "current_discount": None,
                    "status": "error",
                    "error": str(e),
                    "validated_at": datetime.now().isoformat(),
                }

    def _extract_vtex_product_data(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extrai dados do produto do JSON embutido no HTML (padrão VTEX).

        VTEX geralmente armazena dados em:
        - <script type="application/ld+json"> (Schema.org)
        - window.__INITIAL_STATE__ ou window.__RUNTIME__
        """
        # Tentar Schema.org JSON-LD
        script_tags = soup.find_all("script", type="application/ld+json")
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    price = offers.get("price")
                    regular_price = offers.get("highPrice") or price

                    if price and regular_price:
                        discount_pct = (
                            ((regular_price - price) / regular_price) * 100
                            if regular_price > price
                            else 0
                        )
                        return {"price": float(price), "discount_pct": discount_pct}
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        # Tentar window.__INITIAL_STATE__ (VTEX IO)
        script_tags = soup.find_all("script")
        for script in script_tags:
            if script.string and "__INITIAL_STATE__" in script.string:
                # Regex para extrair JSON
                match = re.search(
                    r"__INITIAL_STATE__\s*=\s*({.*?});", script.string, re.DOTALL
                )
                if match:
                    try:
                        data = json.loads(match.group(1))
                        # Navegar pela estrutura VTEX IO (varia por loja)
                        # Exemplo: data['product']['items'][0]['sellers'][0]['price']
                        # (implementação simplificada - pode precisar ajustes por loja)
                        pass
                    except json.JSONDecodeError:
                        continue

        return None

    def _extract_from_html(
        self, soup: BeautifulSoup, store_id: str
    ) -> Optional[Dict]:
        """
        Fallback: extrai preços diretamente do HTML.

        VTEX usa classes CSS diferentes por loja, então precisamos
        de estratégias específicas.
        """
        # Seletores comuns para preços em VTEX
        price_selectors = [
            ".vtex-product-price-1-x-sellingPrice",
            ".vtex-store-components-3-x-sellingPrice",
            '[data-testid="price-value"]',
            ".product-price",
            ".selling-price",
            "[itemprop='price']",
        ]

        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Extrair número do texto (ex: "R$ 19,99" -> 19.99)
                price_match = re.search(r"[\d.,]+", price_text.replace(",", "."))
                if price_match:
                    try:
                        price = float(price_match.group().replace(".", "", price_text.count(".") - 1))
                        # Tentar encontrar preço original (para calcular desconto)
                        original_price_selectors = [
                            ".vtex-product-price-1-x-listPrice",
                            '[data-testid="list-price"]',
                            ".product-list-price",
                            ".old-price",
                        ]
                        original_price = None
                        for orig_selector in original_price_selectors:
                            orig_elem = soup.select_one(orig_selector)
                            if orig_elem:
                                orig_text = orig_elem.get_text(strip=True)
                                orig_match = re.search(
                                    r"[\d.,]+", orig_text.replace(",", ".")
                                )
                                if orig_match:
                                    original_price = float(
                                        orig_match.group().replace(".", "", orig_text.count(".") - 1)
                                    )
                                    break

                        discount_pct = 0
                        if original_price and original_price > price:
                            discount_pct = (
                                (original_price - price) / original_price
                            ) * 100

                        return {"price": price, "discount_pct": discount_pct}
                    except ValueError:
                        continue

        return None

    async def validate_deals_batch(
        self, deals_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Valida um batch de hot deals em paralelo.

        Args:
            deals_df: DataFrame com colunas:
                - product_url
                - promo_price (expected)
                - discount_pct (expected)
                - supermarket (store_id)

        Returns:
            DataFrame original com colunas adicionadas:
                - validation_status
                - current_price_scraped
                - current_discount_scraped
                - is_deal_valid
                - validation_error
                - validated_at
        """
        if deals_df.empty:
            return deals_df

        tasks = []
        for _, row in deals_df.iterrows():
            task = self.validate_deal(
                product_url=row.get("product_url"),
                expected_price=row.get("promo_price", 0),
                expected_discount=row.get("discount_pct", 0),
                store_id=row.get("supermarket", "unknown"),
            )
            tasks.append(task)

        logger.info(f"Validando {len(tasks)} hot deals em paralelo...")
        results = await asyncio.gather(*tasks)

        # Adicionar resultados ao DataFrame
        deals_df["validation_status"] = [r["status"] for r in results]
        deals_df["current_price_scraped"] = [r["current_price"] for r in results]
        deals_df["current_discount_scraped"] = [r["current_discount"] for r in results]
        deals_df["is_deal_valid"] = [r["is_valid"] for r in results]
        deals_df["validation_error"] = [r["error"] for r in results]
        deals_df["validated_at"] = [r["validated_at"] for r in results]

        # Estatísticas
        valid_count = deals_df["is_deal_valid"].sum()
        total_count = len(deals_df)
        logger.info(
            f"Validação concluída: {valid_count}/{total_count} deals válidos ({valid_count/total_count*100:.1f}%)"
        )

        return deals_df


# Helper function para usar em scripts
def validate_hot_deals_sync(deals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Versão síncrona para uso em scripts e notebooks.

    Usage:
        validated_df = validate_hot_deals_sync(hot_deals)
    """
    validator = HotDealValidator()
    return asyncio.run(validator.validate_deals_batch(deals_df))


if __name__ == "__main__":
    # Teste standalone
    import duckdb

    conn = duckdb.connect("data/analytics.duckdb", read_only=True)

    # Pegar sample de hot deals
    hot_deals = conn.execute(
        """
        SELECT
            ap.product_id,
            ap.product_name,
            ds.store_id as supermarket,
            round(ap.promotional_price, 2) as promo_price,
            round(ap.discount_percentage, 1) as discount_pct,
            (SELECT product_url FROM dev_local.tru_product tp
             WHERE tp.product_id = ap.product_id
               AND tp.supermarket = ds.store_id
             LIMIT 1) as product_url
        FROM dev_local.fct_active_promotions ap
        JOIN dev_local.dim_store ds ON ap.store_key = ds.store_key
        WHERE ap.discount_percentage >= 30
        LIMIT 10
    """
    ).df()

    print(f"\n🔍 Validando {len(hot_deals)} hot deals...")
    validated = validate_hot_deals_sync(hot_deals)

    print("\n✅ Resultados:")
    print(
        validated[
            [
                "product_name",
                "promo_price",
                "current_price_scraped",
                "discount_pct",
                "current_discount_scraped",
                "validation_status",
            ]
        ]
    )
