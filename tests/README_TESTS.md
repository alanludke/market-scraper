# Test Suite Documentation

## Overview

Comprehensive test suite for the Market Scraper project, ensuring quality and reliability across all components.

**Coverage Target**: 80%+ (as defined in roadmap)

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                          # Shared fixtures
├── README_TESTS.md                      # This file
├── unit/                                # Unit tests (fast, isolated)
│   ├── test_schemas.py                  # Pydantic schema validation
│   └── test_vtex_scraper.py            # VTEX scraper unit tests
├── integration/                         # Integration tests (slower, with I/O)
│   ├── test_vtex_scraper_e2e.py        # VTEX scraper E2E workflow
│   ├── test_html_scrapers_e2e.py       # HTML scrapers E2E workflow
│   ├── test_parquet_io.py              # Parquet file operations
│   └── test_hot_deals_validation.py    # Hot-deals quality validation
├── fixtures/                            # Test data files
└── test_*.py                           # Additional test modules
```

---

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Fast, isolated tests for individual components.

**Characteristics**:
- No external dependencies (mocked)
- Fast execution (< 1s total)
- Focus on business logic

**Examples**:
```python
# test_schemas.py
def test_vtex_product_schema_valid():
    product = VTEXProduct(**valid_product_data)
    assert product.productId == "100"

def test_vtex_product_schema_invalid_price():
    with pytest.raises(ValidationError):
        VTEXProduct(price=-10.0)  # Negative price
```

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test components working together with real I/O.

**Characteristics**:
- Tests full workflows (discovery → scraping → persistence)
- Uses temp files/databases
- Mocks external APIs
- Slower execution (seconds to minutes)

**Examples**:
```python
# test_vtex_scraper_e2e.py
def test_full_scraping_workflow(vtex_scraper, temp_dir):
    # Discover
    products = vtex_scraper.discover_products(limit=10)

    # Scrape
    vtex_scraper.scrape_region("test_region", products)

    # Verify
    assert (temp_dir / "run_*.parquet").exists()
```

### 3. Hot-Deals Validation Tests

**Purpose**: Ensure promotional deals are legitimate and not fake/inflated.

**Tests**:
- Minimum discount threshold (20%+)
- Price consistency (listPrice > price)
- Suspicious deals detection (>70% discount)
- Temporal persistence (flash deals)
- Quality scoring (0-100)

**See**: `test_hot_deals_validation.py`, `README_HOT_DEALS.md`

---

## Running Tests

### Run All Tests

```bash
# All tests
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Run Specific Categories

```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/integration/test_hot_deals_validation.py

# Specific test function
pytest tests/integration/test_hot_deals_validation.py::TestHotDealsValidation::test_minimum_discount_threshold
```

### Run with Markers/Tags

```bash
# Run only fast tests
pytest tests/ -m "not slow"

# Run only quality tests
pytest tests/ -k "quality"
```

### Debug Mode

```bash
# Show print statements
pytest tests/ -s

# Stop on first failure
pytest tests/ -x

# Show locals on failure
pytest tests/ -l

# Full traceback
pytest tests/ --tb=long
```

---

## Test Fixtures

### Shared Fixtures (`conftest.py`)

**Database Fixtures**:
- `temp_db`: Temporary DuckDB for metrics testing
- `temp_dir`: Temporary directory for file I/O

**Mock Data Fixtures**:
- `mock_vtex_product`: Valid VTEX product response
- `mock_vtex_invalid_product`: Invalid product (for validation testing)
- `mock_vtex_category_tree`: Category tree API response
- `sample_products_batch`: Batch of products for testing

**Configuration Fixtures**:
- `sample_store_config`: Store configuration (Bistek-like)
- `sample_giassi_config`: Store config with category_tree mode

**Metrics Fixtures**:
- `metrics_collector`: Fresh MetricsCollector instance

**Example Usage**:
```python
def test_save_batch(vtex_scraper, sample_products_batch, temp_dir):
    batch_file = temp_dir / "batch.parquet"
    vtex_scraper.save_batch(sample_products_batch, batch_file, "test_region")
    assert batch_file.exists()
```

---

## Test Coverage Goals

### Current Coverage Status

| Module | Target | Notes |
|--------|--------|-------|
| `src/ingest/scrapers/` | 80%+ | Core scraping logic |
| `src/schemas/` | 90%+ | Schema validation |
| `src/observability/` | 70%+ | Metrics & logging |
| `src/analytics/` | 60%+ | Analytics engine |
| **Overall** | **80%+** | Project target |

### Measuring Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html

# Check coverage threshold
pytest tests/ --cov=src --cov-fail-under=80
```

---

## Writing New Tests

### Test Naming Conventions

```python
# ✅ GOOD
def test_scraper_discovers_products_from_sitemap():
    pass

def test_invalid_price_raises_validation_error():
    pass

# ❌ BAD
def test_1():
    pass

def testScraperWorks():
    pass
```

### Test Structure (AAA Pattern)

```python
def test_feature():
    # Arrange: Setup
    scraper = VTEXScraper("test", config)

    # Act: Execute
    result = scraper.discover_products(limit=10)

    # Assert: Verify
    assert len(result) == 10
```

### Parametrized Tests

```python
@pytest.mark.parametrize("discount,expected", [
    (20, True),   # Valid hot-deal
    (10, False),  # Too low
    (80, False),  # Suspicious
])
def test_hot_deal_classification(discount, expected):
    is_hot_deal = discount >= 20 and discount <= 70
    assert is_hot_deal == expected
```

### Mocking External Dependencies

```python
def test_api_call_failure():
    with patch.object(scraper.session, 'get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = scraper._fetch_product(url)
        assert result is None  # Should handle gracefully
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=src --cov-fail-under=80
```

**Status**: To be implemented (see roadmap)

---

## Test Data Management

### Mock vs Real Data

**Use Mocks For**:
- External API calls (VTEX, Osuper)
- Network requests
- Database connections (in unit tests)

**Use Real Data For**:
- Parquet file I/O (integration tests)
- Schema validation (with real product structures)
- End-to-end workflows (with temp files)

### Test Data Generation

```python
# Generate realistic test data
def generate_products(count=10):
    return [
        {
            "productId": str(i),
            "productName": f"Product {i}",
            "price": float(10 + i),
            "brand": f"Brand {i % 5}"
        }
        for i in range(count)
    ]
```

---

## Performance Testing

### Benchmarks

```python
import time

def test_parquet_write_performance():
    df = generate_large_dataframe(10000)

    start = time.time()
    df.to_parquet("test.parquet")
    elapsed = time.time() - start

    assert elapsed < 1.0  # Should complete in <1s
```

### Memory Testing

```python
def test_memory_efficient_batch_processing():
    # Process large dataset in batches
    for batch in iter_batches(large_dataset, batch_size=100):
        process(batch)
        # Memory should not grow unbounded
```

---

## Troubleshooting

### Common Issues

**1. Import Errors**:
```bash
# Solution: Run tests from project root
cd /path/to/market_scraper
pytest tests/
```

**2. Fixture Not Found**:
```python
# Solution: Ensure conftest.py is in tests/ directory
tests/conftest.py  # ✅
tests/integration/conftest.py  # ❌ (fixtures won't be shared)
```

**3. Slow Tests**:
```bash
# Solution: Run only fast tests
pytest tests/ -m "not slow"

# Or run in parallel
pytest tests/ -n auto  # Requires pytest-xdist
```

**4. Flaky Tests**:
```python
# Solution: Use retry decorator
@pytest.mark.flaky(reruns=3)
def test_flaky_api_call():
    pass
```

---

## Quality Metrics

### Test Quality Checklist

- [ ] Tests are independent (can run in any order)
- [ ] Tests are deterministic (same input = same output)
- [ ] Tests are fast (< 1s for unit, < 10s for integration)
- [ ] Tests have clear assertion messages
- [ ] Tests clean up after themselves (temp files, connections)
- [ ] Tests follow AAA pattern (Arrange, Act, Assert)

### Code Review Checklist for Tests

- [ ] New feature has corresponding tests
- [ ] Edge cases are tested (null, empty, extreme values)
- [ ] Error paths are tested (exceptions, failures)
- [ ] Tests are not duplicated
- [ ] Mocks are used appropriately (not over-mocked)

---

## Related Documentation

- **Testing Strategy**: `docs/quality/TESTING_STRATEGY.md`
- **Project Quality Standards**: `docs/quality/PROJECT_QUALITY_STANDARDS.md`
- **Hot-Deals Testing**: `src/transform/dbt_project/models/marts/pricing_marts/README_HOT_DEALS.md`
- **CI/CD Setup**: (TBD - part of roadmap)

---

## Future Enhancements

### Planned

- [ ] Increase coverage to 90%+
- [ ] Add property-based testing (Hypothesis)
- [ ] Add mutation testing (mutmut)
- [ ] Performance regression tests
- [ ] Visual regression tests (screenshots)
- [ ] Contract tests (API schemas)

### Long Term

- [ ] Integration with Prefect for scheduled test runs
- [ ] Test data versioning (DVC)
- [ ] Test analytics dashboard (track flakiness, duration trends)

---

**Last Updated**: 2026-02-07
**Maintained By**: Data Team
**Questions?**: See project README or open an issue

---

## Quick Reference

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src

# Run fast tests only
pytest tests/unit/

# Run specific test
pytest tests/integration/test_hot_deals_validation.py

# Debug mode
pytest tests/ -s -x -vv

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
```
