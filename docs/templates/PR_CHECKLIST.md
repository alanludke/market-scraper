# Pull Request Checklist Template

Use this checklist when creating or reviewing pull requests to ensure quality and completeness.

---

## PR Title Format

```
<type>: <short description>

Examples:
feat: add Angeloni supermarket scraper
fix: handle empty struct fields in Parquet serialization
docs: update DATA_LAYERS.md with serving layer examples
refactor: simplify VTEXScraper deduplication logic
test: add integration tests for pricing pipeline
```

---

## PR Description Template

```markdown
## Description
Brief description of what this PR does and why.

## Type of Change
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test addition/update

## Changes Made
- Bullet point list of specific changes
- Be concise but complete

## Related Issues
Closes #<issue_number>
Relates to #<issue_number>

---

## Testing

### Python Code
- [ ] Unit tests pass (`pytest tests/`)
- [ ] Integration tests pass
- [ ] Manual testing performed
- [ ] No new warnings or errors

### DBT Models
- [ ] `dbt parse` passes
- [ ] `dbt compile --select <model>` successful
- [ ] `dbt test --select <model>` all tests pass
- [ ] `dbt run --select <model>` materializes correctly

### Code Quality
- [ ] sqlfluff lint passes (`sqlfluff lint models/`)
- [ ] yamllint passes (`yamllint models/`)
- [ ] No syntax errors or typos
- [ ] Code follows project style guide

---

## Data Quality

### For New/Modified Models
- [ ] Row counts validated (compare to expected)
- [ ] NULL values explained (documented why nulls exist)
- [ ] No data loss detected (compare before/after)
- [ ] Sample queries tested
- [ ] Edge cases handled (empty results, missing columns, etc.)

### For New Data Sources
- [ ] EDA completed ([EDA_TEMPLATE.md](./EDA_TEMPLATE.md))
- [ ] Data quality tests defined
- [ ] Freshness checks configured
- [ ] Volume estimates documented

---

## Documentation

### Code Documentation
- [ ] Functions have docstrings (Python)
- [ ] Complex logic has inline comments
- [ ] SQL CTEs have descriptive names
- [ ] No TODOs or FIXMEs left unaddressed

### DBT Documentation
- [ ] Model has `description` in `schema.yml`
- [ ] All columns documented
- [ ] Meta tags complete (`graining`, `owner`, `kpis`, etc.)
- [ ] Tests defined for critical columns

### Project Documentation
- [ ] CLAUDE.md updated if architecture changed
- [ ] README updated if usage changed
- [ ] CHANGELOG updated (if applicable)
- [ ] New docs created (if new feature)

---

## Schema & Contracts

### For Trusted/Marts Models
- [ ] Contract enforced (`contract: {enforced: true}`)
- [ ] Data types explicit (`data_type: varchar/double/boolean`)
- [ ] Primary keys have `unique` + `not_null` tests
- [ ] Foreign keys have `relationships` tests
- [ ] No breaking changes to downstream models

### Schema Change Checklist
- [ ] Backward compatible (or migration plan exists)
- [ ] Downstream models tested
- [ ] Dashboards/reports updated
- [ ] Stakeholders notified

---

## Performance

- [ ] No unnecessary full table scans
- [ ] Filters applied early (WHERE clauses)
- [ ] Incremental models use proper watermark
- [ ] Query execution time is acceptable
- [ ] No memory issues during compilation/materialization

---

## Security & Privacy

- [ ] No secrets or credentials in code
- [ ] `.env` used for sensitive data
- [ ] No PII exposed (or documented if necessary)
- [ ] Access controls considered
- [ ] Compliance requirements met (GDPR, etc.)

---

## Git Best Practices

- [ ] Branch name follows convention (`feature/`, `bugfix/`, `hotfix/`)
- [ ] Commits are atomic and focused
- [ ] Commit messages are clear and descriptive
- [ ] No merge conflicts
- [ ] Based on latest `master` branch

---

## Deployment Considerations

- [ ] Runs successfully in CI/CD pipeline
- [ ] No hardcoded paths or environment-specific values
- [ ] Backward compatible with prod environment
- [ ] Rollback plan exists (if high-risk change)
- [ ] Monitoring/alerts configured (if needed)

---

## Review Process

### For Authors
Before requesting review:
1. Self-review code changes
2. Run all tests locally
3. Complete this checklist
4. Add reviewers and labels

### For Reviewers
Focus areas:
1. **Correctness**: Does it do what it's supposed to?
2. **Readability**: Is the code easy to understand?
3. **Testing**: Are tests adequate and passing?
4. **Documentation**: Is it well-documented?
5. **Performance**: Any obvious bottlenecks?

---

## Example: Complete Checklist

```markdown
## Description
Add Angeloni supermarket to scraping pipeline.

## Type of Change
- [x] New feature

## Changes Made
- Added Angeloni to `config/stores.yaml`
- Created `stg_angeloni__products` model
- Updated `tru_product` to include Angeloni
- Added data quality tests

## Related Issues
Closes #42

---

## Testing
- [x] Unit tests pass
- [x] `dbt test` passes (5/5 tests)
- [x] Manual scrape successful (8K products)
- [x] sqlfluff lint clean

## Data Quality
- [x] Row counts: 8K products × 12 regions = 96K rows ✓
- [x] NULL values: brand can be null (documented)
- [x] No data loss: All products scraped
- [x] Freshness: <24h ✓

## Documentation
- [x] Model description added
- [x] All columns documented
- [x] Meta tags: `graining`, `owner`, `access_type`
- [x] CLAUDE.md updated (new store added)

## Schema & Contracts
- [x] Contract enforced in `tru_product`
- [x] Primary key: `product_id + region + date`
- [x] Tests: `unique`, `not_null`, `accepted_values`

## Performance
- [x] Scrape time: 45 seconds (acceptable)
- [x] DBT run time: 8 seconds (full refresh)
- [x] Incremental model configured

## Security
- [x] API key in `.env` (not committed)
- [x] No PII (public pricing only)

## Git
- [x] Branch: `feature/add-angeloni-scraper`
- [x] Based on latest `master`
- [x] No conflicts

## Deployment
- [x] CI pipeline passes
- [x] No hardcoded paths
- [x] Backward compatible

**Decision**: ✅ Ready for merge
```

---

## Post-Merge Checklist

After PR is merged:

- [ ] Delete feature branch (local and remote)
- [ ] Monitor production logs for errors
- [ ] Verify data quality in prod
- [ ] Update project board/tracker
- [ ] Notify stakeholders (if customer-facing)

---

## Resources

- [Git Flow](../development/GIT_FLOW.md)
- [Testing Strategy](../quality/TESTING_STRATEGY.md)
- [Code Review Best Practices](https://google.github.io/eng-practices/review/)
