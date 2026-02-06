# VTEX API Limits and Best Practices

Official VTEX API documentation: https://developers.vtex.com/docs/api-reference

## Rate Limits

### Catalog API (Products)
- **Rate limit**: 5,000 requests/minute per account
- **Burst**: Up to 100 concurrent requests
- **Recommended delay**: 0.5-1 second between requests to avoid throttling

### Search API
- **Endpoint**: `/api/catalog_system/pub/products/search`
- **Max products per request**: 50 (`_from=0&_to=49`)
- **Max pagination offset**: 2,500 products
- **Response codes**:
  - `200`: Success (all products returned)
  - `206`: Partial Content (reached page limit)
  - `429`: Too Many Requests (rate limited)
  - `503`: Service Unavailable (VTEX maintenance)

### Category Tree API
- **Endpoint**: `/api/catalog_system/pub/category/tree/{level}`
- **No explicit rate limit**, but same 5k/min account limit applies
- **Levels**: 1 (categories), 2 (subcategories), 3 (departments)

### Sitemap
- **Endpoint**: `/sitemap.xml` or `/sitemap/*.xml`
- **No rate limit** (static files served by CDN)
- **Fastest discovery method** for stores with sitemaps

## API Response Structure

### Product Search Response
```json
[
  {
    "productId": "1",
    "productName": "Product Name",
    "brand": "Brand Name",
    "link": "/product-name/p",
    "linkText": "product-name",
    "items": [
      {
        "itemId": "1",
        "name": "SKU Name",
        "ean": "1234567890123",
        "sellers": [
          {
            "sellerId": "1",
            "sellerName": "Seller Name",
            "commertialOffer": {
              "Price": 10.99,
              "ListPrice": 12.99,
              "AvailableQuantity": 100
            }
          }
        ],
        "images": [
          {
            "imageId": "img-1",
            "imageUrl": "https://cdn.vtex.com/image.jpg"
          }
        ]
      }
    ]
  }
]
```

## Regional Pricing (Segment Cookies)

VTEX uses `vtex_segment` cookies to control region-specific pricing:

### Segment Cookie Structure
```json
{
  "campaigns": null,
  "channel": "1",
  "priceTables": null,
  "regionId": "v2.5BE6A0CEC1DA8E9954E2",
  "currencyCode": "BRL",
  "currencySymbol": "R$",
  "countryCode": "BRA",
  "cultureInfo": "pt-BR",
  "channelPrivacy": "public"
}
```

### How to Get Region ID
1. **API call**: `/api/checkout/pub/regions?country=BRA&postalCode={cep}&sc={salesChannel}`
2. **Response**: `[{"id": "v2.5BE6A0CEC1DA8E9954E2", "sellers": [...]}]`
3. **Fallback**: Use hub_id if regions API returns empty

### Sales Channels (sc parameter)
- `sc=1`: Default channel (usually main store)
- `sc=2`: Secondary channel (e.g., marketplace)
- Store-specific: Check `/admin/Site/SalesChannel.aspx` in VTEX admin

## Discovery Strategies

### 1. Sitemap (Fastest ⚡)
**When to use**: Store has `/sitemap.xml` with product URLs
**Pros**:
- Single HTTP request to get all product IDs
- No rate limiting (CDN-served)
- Most reliable

**Cons**:
- Not all VTEX stores maintain sitemaps
- May include discontinued products

**Implementation**:
```python
sitemap_url = f"{base_url}/sitemap.xml"
response = session.get(sitemap_url)
root = ET.fromstring(response.content)
urls = [loc.text for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
product_ids = [extract_id_from_url(url) for url in urls if '/p' in url]
```

### 2. Category Tree (Most Complete 📦)
**When to use**: Need to discover all active products
**Pros**:
- Only returns active products
- Can filter by department
- Respects regional availability

**Cons**:
- Multiple API calls required
- Slower than sitemap
- 2,500 product pagination limit per category

**Implementation**:
```python
# Get departments
depts = session.get(f"{base_url}/api/catalog_system/pub/category/tree/3").json()

for dept in depts:
    offset = 0
    while offset < 2500:
        products = session.get(
            f"{base_url}/api/catalog_system/pub/products/search",
            params={"fq": f"C:{dept['id']}", "_from": offset, "_to": offset + 49}
        ).json()

        if not products:
            break

        offset += 50
        time.sleep(0.5)  # Respect rate limits
```

## Current Implementation

Our scraper respects all VTEX limits:

- ✅ **Batch size**: 50 products per request
- ✅ **Request delay**: 0.5s configurable per store
- ✅ **Pagination**: Stops at 2,500 offset
- ✅ **Error handling**: Retries on 429/503
- ✅ **Regional pricing**: Segment cookies per region
- ✅ **Discovery modes**: Both sitemap and category_tree

### Configuration (config/stores.yaml)
```yaml
bistek:
  base_url: "https://www.bistek.com.br"
  discovery: "sitemap"          # or "category_tree"
  global_discovery: true         # Discover once, scrape per region
  batch_size: 50                 # Max 50 per VTEX API limits
  request_delay: 0.5             # 0.5s between requests (conservative)
  cookie_domain: ".bistek.com.br"
```

## Error Handling

### HTTP Status Codes
- **429 Too Many Requests**: Exponential backoff (2s → 4s → 8s)
- **503 Service Unavailable**: VTEX maintenance, retry after 60s
- **206 Partial Content**: Normal pagination response
- **404 Not Found**: Product deleted, skip and log

### Validation Errors (Phase 2)
All products are validated against official VTEX API schema before saving:
- Invalid products are logged and skipped
- Validation errors tracked in `runs.duckdb`
- Ensures data quality in bronze layer

## Performance Benchmarks

Based on our metrics (Phase 1):

| Store  | Discovery Mode | Products | Regions | Avg Time/Region | Total Time |
|--------|---------------|----------|---------|-----------------|------------|
| Bistek | sitemap       | 13,156   | 13      | ~5 min          | ~65 min    |
| Fort   | category_tree | 10,390   | 7       | ~8 min          | ~56 min    |
| Giassi | category_tree | varies   | 17      | ~6 min          | ~102 min   |

**Bottleneck**: API response time (1-2s avg), not our code
**Optimization**: Parallelizing regions (done in Phase 1)

## References

- **VTEX Developers**: https://developers.vtex.com/
- **Catalog API**: https://developers.vtex.com/docs/api-reference/catalog-api
- **Search API**: https://developers.vtex.com/docs/api-reference/search-api
- **Checkout API** (regions): https://developers.vtex.com/docs/api-reference/checkout-api

---

**Last updated**: 2026-02-05
**Phase**: 2 (Data Quality with Pydantic validation)
