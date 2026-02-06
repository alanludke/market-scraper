# Discovery Strategies: Sitemap vs Category Tree

## TL;DR - Recommendation

**For production**: Use **Sitemap** when available (faster, 1 request), fallback to **Category Tree** if sitemap doesn't exist.

**Speed**: Sitemap (1 request, ~2s) >> Category Tree (10-50 requests, ~30-120s)

**Completeness**: Category Tree (100% active products) > Sitemap (may include discontinued)

---

## Detailed Comparison

### 1. Sitemap Discovery

#### How It Works
```python
# Single HTTP request to sitemap XML
GET https://www.bistek.com.br/sitemap/sitemap-products.xml

# Parse URLs:
# https://www.bistek.com.br/arroz-integral-tio-joao-1kg/p
# Extract product ID from URL (via second request or regex)
```

#### Pros
- ✅ **Extreme speed**: 1 single request to discover ALL products
  - Bistek: ~2-3 seconds to discover 10,000 products
- ✅ **API efficiency**: 1 request vs 50+ requests (category tree)
- ✅ **CDN-cached**: Sitemap served via CDN (99.9% uptime, low latency)
- ✅ **No pagination**: No need to iterate pages (doesn't hit 2,500 limit)
- ✅ **No rate limit risk**: 1 request doesn't violate VTEX limits

#### Cons
- ❌ **May include discontinued products**: Sitemap may not be updated in real-time
  - Product removed from catalog at 14:00 may appear in sitemap until rebuild
  - Sitemap rebuild: usually 1x/day (00:00)
- ❌ **Not all stores have sitemap**: ~30% of VTEX stores don't implement it
  - Bistek: ✅ HAS (`/sitemap/sitemap-products.xml`)
  - Fort: ❌ NO (returns 404)
  - Giassi: ❌ NO (returns 404)
- ❌ **Doesn't respect region availability**: Discovers global products, but some may not be available in certain regions
  - Ex: Product X in sitemap, but unavailable in Florianopolis
  - Workaround: Filter products with `AvailableQuantity == 0` after scraping

#### Performance Benchmark (Bistek)
```
Discovery via sitemap:
  - Request sitemap XML: ~1.2s
  - Parse XML (10,347 URLs): ~0.8s
  - Total: ~2s

Discovery via category_tree:
  - Fetch category tree: ~1s
  - Iterate 12 departments: ~15 requests (3 pages/dept average)
  - Total: ~30-45s

SPEEDUP: 15-22x faster!
```

---

### 2. Category Tree Discovery

#### How It Works
```python
# 1. Fetch category tree
GET /api/catalog_system/pub/category/tree/3

# Response: [{id: 1, name: "Food", hasChildren: true, children: [...]}]

# 2. For each department (leaf category):
for dept_id in [1, 2, 3, ...]:
    # Paginate through products
    for page in range(0, 2500, 50):  # 50 products per page
        GET /api/catalog_system/pub/products/search?fq=C:/{dept_id}/&_from={page}&_to={page+49}
```

#### Pros
- ✅ **100% active products**: Only discovers **currently available** products
  - API returns only products with active sellers
- ✅ **Respects region availability**: If using `vtex_segment` cookie, only returns products available in region
  - Ex: Giassi Florianopolis vs Giassi Joinville (different catalogs)
- ✅ **Always works**: All VTEX stores have category tree (doesn't depend on sitemap)
- ✅ **Extra metadata**: Response already includes price, stock (can save requests later)

#### Cons
- ❌ **Much slower**: 10-50 requests (1 per department, multiple pages)
  - Giassi: 17 departments x 3 pages average = **51 requests** (~120s discovery)
- ❌ **Rate limit risk**: 50 requests consume 1% of rate limit (5,000 req/min)
- ❌ **Pagination limit**: Max offset = 2,500 products per category
  - If department has 3,000 products → loses 500 products!
  - Workaround: Subcategories (go deeper in tree)
- ❌ **Regional variation**: If `global_discovery=false`, needs to discover PER REGION
  - Giassi: 17 regions x 51 requests = **867 requests** just for discovery! (3-5 min)

#### Performance Benchmark (Fort)
```
Discovery via category_tree (global_discovery=true):
  - Fetch category tree: ~1s
  - Iterate 7 departments: ~21 requests (3 pages/dept)
  - Total: ~30s

Discovery via category_tree (global_discovery=false, Giassi):
  - Per region (17 regions):
    - Fetch category tree: ~1s
    - Iterate 17 departments: ~51 requests
    - Total per region: ~120s
  - Total all regions: ~34 min (!!!)

SLOWDOWN: 15-20x slower than sitemap
```

---

## 3. Hybrid Strategy (Recommendation)

### Current Implementation (Bistek)
```yaml
# config/stores.yaml
bistek:
    discovery: "sitemap"
    global_discovery: true  # 1 global discovery, scrape per region
```

**Flow**:
1. Discovery: Sitemap → 10,347 product IDs (2s)
2. Scrape: For each region (13 regions):
   - Set region cookie (`vtex_segment`)
   - Batch fetch 10,347 products (50 products/batch = 207 batches)
   - Duration per region: ~8-10 min (with conservative rate limiter)
   - **Total**: ~2h for 13 regions (sequential)
   - **With parallelism (max_workers=13)**: ~10 min TOTAL!

**Detected problem**: May scrape products not available in region
- Ex: Product X in sitemap, but `AvailableQuantity=0` in Florianopolis
- **Solution**: Filter after scraping (quality check)

### Current Implementation (Giassi)
```yaml
giassi:
    discovery: "category_tree"
    global_discovery: false  # Discovery PER REGION
```

**Flow**:
1. For each region (17 regions):
   - Set region cookie
   - Discovery via category tree: ~51 requests (~120s)
   - Scrape discovered products: ~15 min
   - **Total per region**: ~17 min
2. **Total all regions**: ~5h (sequential) or ~17 min (parallel)

**Why `global_discovery=false`?**
- Giassi has **different regional catalogs** (product X in Florianopolis, but not in Joinville)
- Sitemap not available → can't do global discovery

---

## 4. Alternative Strategies

### 4.1. Hybrid Sitemap + Category Tree (RECOMMENDED)

**Logic**:
```python
def discover_products(store_config):
    # Try sitemap first (fast path)
    try:
        product_ids = discover_via_sitemap()
        logger.info(f"Discovered {len(product_ids)} via sitemap")
        return product_ids
    except SitemapNotFoundError:
        logger.warning("Sitemap not available, falling back to category tree")
        return discover_via_category_tree()
```

**Benefit**:
- ✅ Best of both worlds: sitemap speed when available
- ✅ Automatic fallback if sitemap doesn't exist
- ✅ Zero manual config changes

**Implementation**: Modify `VTEXScraper.run()` to try sitemap first

---

### 4.2. Incremental Discovery (Delta Scraping)

**Problem**: Re-scraping 10,000 products daily is wasteful if only 50 changed

**Solution**: Discover only **new or modified** products

**VTEX API offers**:
```python
# Products added/modified after date
GET /api/catalog_system/pub/products/search?fq=createdFrom:2026-02-05T00:00:00Z
GET /api/catalog_system/pub/products/search?fq=modifiedFrom:2026-02-05T00:00:00Z
```

**Flow**:
1. **Initial run** (full scrape): Discover all 10,000 products via sitemap
2. **Subsequent runs** (delta scrape):
   - Discover only products modified since last run
   - Ex: 2026-02-06 00:00 → query `modifiedFrom:2026-02-05T06:00:00Z`
   - Result: ~50-200 products/day (vs 10,000)
3. **Scrape**: Only delta products (saves 98% of requests!)

**Benefit**:
- ✅ **98% fewer requests**: 200 products vs 10,000
- ✅ **50x faster**: 2 min vs 1.5h
- ✅ **Lower rate limit risk**: Low request volume

**Trade-off**:
- ❌ Need to track `last_run_timestamp` (metadata in DuckDB)
- ❌ Full scrape 1x/week (ensure consistency)

**When to use**: **Daily** scraping (not one-off)

---

### 4.3. Smart Sampling (Category-Based)

**Problem**: Not all products are equally important

**Solution**: Prioritize high-volume categories

**Logic**:
```python
# Analytics: identify most important categories
SELECT category_id, COUNT(*) as products, SUM(price_changes) as volatility
FROM silver.products
GROUP BY category_id
ORDER BY volatility DESC
LIMIT 5

# Discovery: focus on these 5 categories
priority_categories = [1, 3, 7, 12, 15]  # Food, Beverages, etc
for cat_id in priority_categories:
    products = discover_category(cat_id)
    scrape(products)
```

**Benefit**:
- ✅ Focused scraping on high-priority products
- ✅ 80/20 rule: 20% categories = 80% of analytical value

**When to use**: Limited API call budget, focus on specific KPIs

---

## 5. Recommendation by Store

### Bistek
**Current**: Sitemap + Global Discovery ✅ **OPTIMAL**

**Justification**:
- Sitemap available (maximum speed)
- Uniform catalog across regions (global discovery works)
- 13 regions x 10K products = high volume (sitemap saves 200+ requests)

**Suggested optimization**: None! Already ideal.

---

### Fort
**Current**: Category Tree + Global Discovery ⚠️ **CAN IMPROVE**

**Detected problem**: Sitemap NOT tested (assumed doesn't exist)

**Recommended test**:
```bash
curl -I https://www.fortattacadista.com.br/sitemap/sitemap-products.xml
# If returns 200 → USE SITEMAP!
```

**If sitemap exists**:
```yaml
fort:
    discovery: "sitemap"  # CHANGE from category_tree
    global_discovery: true
```

**Expected speedup**: 15-20x (30s → 2s discovery)

---

### Giassi
**Current**: Category Tree + Per-Region Discovery ⚠️ **NECESSARY BUT SLOW**

**Problem**: Different regional catalogs (can't use global discovery)

**Optimization 1 - Aggressive parallelism**:
```yaml
giassi:
    max_workers: 17  # 1 thread per region (parallelize discovery!)
    request_delay: 0.05  # More aggressive (monitor 429 errors)
```

**Expected result**:
- Current: ~5h (17 sequential regions)
- Optimized: ~20-30 min (17 parallel regions)

**Optimization 2 - Incremental discovery**:
- Full scrape: 1x/week (Sunday 00:00)
- Delta scrape: Daily (Mon-Sat, only modified products)
- **Speedup**: 50x on daily runs (30 min → 30s)

---

## 6. Trade-off Analysis

| Strategy | Speed | Completeness | API Calls | Complexity | When to Use |
|----------|-------|--------------|-----------|------------|-------------|
| **Sitemap** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | Store with sitemap, uniform catalog |
| **Category Tree (global)** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | No sitemap, uniform catalog |
| **Category Tree (per-region)** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | Different regional catalogs |
| **Hybrid (sitemap fallback)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | **RECOMMENDED** (production) |
| **Incremental (delta)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Daily scraping, high volume |

---

## 7. Recommended Implementation (Next Steps)

### Step 1: Test Fort Sitemap
```bash
# Check if Fort has sitemap
curl -I https://www.fortattacadista.com.br/sitemap/sitemap-products.xml

# If 200 OK → update config/stores.yaml
fort:
    discovery: "sitemap"
    global_discovery: true
```

### Step 2: Implement Hybrid Discovery (VTEXScraper)
```python
# src/ingest/scrapers/vtex.py

def run(self, region_keys: list[str] = None, limit: int = None):
    # ... existing setup ...

    # NEW: Try sitemap first, fallback to category_tree
    try:
        if self.discovery == "sitemap":
            product_ids = self._discover_via_sitemap(limit)
        else:
            raise SitemapNotAvailableError()
    except (SitemapNotAvailableError, requests.HTTPError):
        logger.warning(
            f"Sitemap not available for {self.store_name}, falling back to category tree"
        )
        product_ids = self._discover_via_categories(limit)

    logger.info(f"Discovered {len(product_ids)} products", discovery_method=self.discovery)

    # ... rest of scraping logic ...
```

### Step 3: Add Incremental Discovery (Optional - Phase 4)

**DBT Watermarking**:
```sql
-- models/bronze/last_scrape_timestamp.sql
SELECT MAX(scraped_at) as last_run
FROM {{ source('bronze', 'products_parquet') }}
WHERE store = '{{ var("store_name") }}'
```

**VTEXScraper Delta Discovery**:
```python
def _discover_delta_products(self, since: datetime) -> list[str]:
    """Discover products modified since timestamp."""
    api_url = f"{self.base_url}/api/catalog_system/pub/products/search"
    params = {
        "fq": f"modifiedFrom:{since.isoformat()}",
        "_from": 0,
        "_to": 2500
    }
    resp = self.session.get(api_url, params=params)
    products = resp.json()
    return [p['productId'] for p in products]
```

---

## 8. Future Extensibility (Multi-Platform)

### Design Considerations

**Current**: All stores use VTEX platform (Bistek, Fort, Giassi)

**Future**: Multiple platforms beyond VTEX
- Non-VTEX stores (e.g., custom e-commerce, Magento, Shopify)
- Data sources beyond product catalogs (promotions, reviews, inventory)
- Multiple supermarket chains (10+ stores)

### Platform Abstraction Strategy

**BaseScraper** (already exists):
- Platform-agnostic interface
- Discovery, scraping, and validation methods
- Subclass for each platform

**VTEXScraper** (current):
- Implements VTEX-specific discovery (sitemap, category_tree)
- Handles VTEX segment cookies, API limits

**Future scrapers**:
```python
# src/ingest/scrapers/magento.py
class MagentoScraper(BaseScraper):
    """Scraper for Magento-based stores."""

    def _discover_products(self):
        # Magento REST API discovery
        return self._magento_category_discovery()

    def _fetch_products(self, product_ids):
        # Magento API batch fetch
        pass

# src/ingest/scrapers/shopify.py
class ShopifyScraper(BaseScraper):
    """Scraper for Shopify-based stores."""

    def _discover_products(self):
        # Shopify GraphQL discovery
        return self._shopify_collection_discovery()
```

**Store configuration**:
```yaml
# config/stores.yaml

# VTEX stores (existing)
bistek:
    platform: "vtex"
    discovery: "sitemap"
    # ... VTEX-specific config

# Future: Non-VTEX store
carrefour:
    platform: "custom"  # Custom e-commerce
    discovery: "api"
    api_endpoint: "https://api.carrefour.com.br/products"
    auth_method: "bearer_token"

walmart:
    platform: "shopify"
    discovery: "graphql"
    shop_domain: "walmart.com.br"
```

**Scraper Factory Pattern**:
```python
# src/ingest/scrapers/factory.py

def create_scraper(store_name: str, config: dict):
    """Factory to create appropriate scraper based on platform."""
    platform = config.get("platform", "vtex")

    if platform == "vtex":
        return VTEXScraper(store_name, config)
    elif platform == "magento":
        return MagentoScraper(store_name, config)
    elif platform == "shopify":
        return ShopifyScraper(store_name, config)
    elif platform == "custom":
        return CustomAPIScraper(store_name, config)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
```

### Data Source Abstraction

**Current**: Only product catalog scraping

**Future**: Multiple data sources per store
- Product catalogs (prices, descriptions, images)
- Promotions/offers (weekly flyers, coupons)
- Inventory levels (real-time stock)
- Customer reviews/ratings
- Store locations/hours

**Multi-Source Architecture**:
```python
# src/ingest/sources/

# Base source interface
class DataSource(ABC):
    @abstractmethod
    def extract(self) -> pd.DataFrame:
        pass

# Product catalog source (existing)
class ProductCatalogSource(DataSource):
    def __init__(self, scraper: BaseScraper):
        self.scraper = scraper

    def extract(self) -> pd.DataFrame:
        return self.scraper.run()

# Promotion source (future)
class PromotionSource(DataSource):
    def extract(self) -> pd.DataFrame:
        # Scrape weekly flyers, parse PDFs, etc
        pass

# Inventory source (future)
class InventorySource(DataSource):
    def extract(self) -> pd.DataFrame:
        # Real-time inventory API
        pass
```

**Store with multiple sources**:
```yaml
bistek:
    platform: "vtex"
    sources:
        - type: "product_catalog"
          discovery: "sitemap"
          schedule: "daily 06:00"

        - type: "promotions"
          method: "pdf_scrape"
          url: "https://bistek.com.br/ofertas-da-semana.pdf"
          schedule: "weekly monday 00:00"

        - type: "inventory"
          api_endpoint: "https://api.bistek.com.br/inventory"
          schedule: "hourly"
```

**Medallion per source**:
```
data/
├── bronze/
│   ├── product_catalog/
│   │   └── supermarket=bistek/region=X/date=Y/
│   ├── promotions/
│   │   └── supermarket=bistek/date=Y/
│   └── inventory/
│       └── supermarket=bistek/timestamp=Y/
├── silver/
│   ├── products/          # Joined catalog + inventory
│   ├── prices/            # Historical prices
│   └── promotions/        # Cleaned promotions
└── gold/
    ├── price_index/       # Aggregated price trends
    ├── promotion_impact/  # Promotion effectiveness
    └── competitiveness/   # Cross-store comparisons
```

### Scalability Considerations

**Current**: 3 stores, ~30K unique products, ~11GB historical data

**Target (12 months)**: 10-20 stores, ~100K unique products, ~50GB data

**Optimizations needed**:
1. **Incremental processing** (delta scraping) - avoid re-scraping unchanged data
2. **Distributed rate limiting** (if running parallel scrapers on multiple machines)
3. **Cloud storage tiering** (hot → cool → archive lifecycle)
4. **Partitioning strategy** (by date, store, region for query performance)

**Infrastructure changes** (when reaching 10+ stores):
- Prefect Cloud (vs local Prefect) - centralized orchestration
- Azure Container Instances (vs local cron) - scalable execution
- Redis (vs in-memory rate limiter) - distributed rate limiting
- Great Expectations Cloud (vs local) - centralized data quality monitoring

---

## 9. Conclusion

### For Bistek (already optimized)
✅ **Continue using sitemap + global discovery**
- Already ideal (2s discovery, 10K products)
- With parallelism (max_workers=13): ~10 min total

### For Fort (easy optimization)
⚠️ **Test if sitemap exists**
- If yes: switch to sitemap (15-20x speedup)
- If no: keep category_tree

### For Giassi (optimization needed)
⚠️ **Increase parallelism**
- `max_workers: 17` (1 thread/region)
- Expected speedup: 5h → 20 min

**Optional - Future**:
- Incremental discovery (delta scraping)
- Hybrid sitemap fallback (automatic)
- Multi-platform support (Magento, Shopify, custom APIs)
- Multi-source ingestion (promotions, inventory, reviews)

---

**Last updated**: 2026-02-06
**Version**: 1.0 (Discovery Strategy Analysis + Future Extensibility)
