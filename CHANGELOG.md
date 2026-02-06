# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Incremental models with watermarking
- DBT snapshots (SCD Type 2) for price history
- Dimensional modeling (facts & dimensions)
- Streamlit operational dashboard
- Prefect orchestration

---

## [2.0.0] - 2026-02-05

### 🎉 Major Release - Production-Ready Platform

This release represents a complete refactor of the Market Scraper platform with enterprise-grade data engineering practices, comprehensive documentation, and automated quality enforcement.

### Added

#### Architecture & Infrastructure
- **Medallion Architecture**: Implemented 5-layer data architecture (Raw → Staging → Trusted → Marts → Serving)
- **DBT Project**: Full DBT transformation pipeline with DuckDB adapter
- **Parquet Storage**: Migrated from JSONL to Parquet (35x faster, 600x smaller)
- **Quality Enforcement**: SQLFluff, yamllint, pre-commit hooks, CI/CD pipelines

#### Documentation (11 Documents)
- **Architecture Guides**:
  - `ARCHITECTURE.md` - System design & data flow
  - `DATA_LAYERS.md` - Medallion architecture (5 layers)
  - `SNAPSHOTS.md` - Historical tracking (SCD Type 2)
  - `INCREMENTAL_MODELS.md` - Performance optimization strategies
- **Templates**:
  - `EDA_TEMPLATE.md` - Exploratory data analysis checklist
  - `KPI_MATRIX.md` - KPI documentation template
  - `PR_CHECKLIST.md` - Pull request review guide
  - `KIMBALL_BUS_MATRIX.md` - Dimensional modeling template
  - `LOGICAL_DATA_MODEL.md` - ERD template with Mermaid
- **Quality & Testing**:
  - `TESTING_STRATEGY.md` - DBT testing guide
  - `PROJECT_QUALITY_STANDARDS.md` - Quality enforcement standards

#### Quality Configs
- `.sqlfluff` - SQL linting for DuckDB + DBT templater
- `.yamllint` - YAML validation rules
- `.pre-commit-config.yaml` - 15+ automated checks (dbt-checkpoint, sqlfluff, yamllint)

#### CI/CD
- `.github/workflows/lint.yml` - SQL + YAML linting on PRs
- `.github/workflows/test.yml` - DBT parse/compile/test on PRs

#### Project Files
- `README.md` - Comprehensive project documentation
- `CONTRIBUTING.md` - Contribution guidelines
- `CONTRIBUTORS.md` - Contributors list
- `LICENSE` - MIT License
- `CHANGELOG.md` - Version history (this file)
- `.gitattributes` - Line ending normalization

### Changed

#### Breaking Changes
- **Storage Format**: JSONL → Parquet (migration required)
- **Directory Structure**: Reorganized to `src/ingest`, `src/transform`, `src/analytics`
- **DBT Location**: Moved to `src/transform/dbt_project/`
- **Email References**: Changed to generic `data-engineering@market-scraper.local`

#### Improvements
- **Scraper Performance**: Thread-safe parallel execution
- **Data Quality**: Automatic empty struct cleaning in Parquet writer
- **Naming Conventions**: Enforced `stg_*`, `tru_*`, `fct_*`, `dim_*` prefixes
- **Documentation Coverage**: 100% models + columns documented

### Removed
- **Legacy Scrapers**: Moved to `archive/legacy_scrapers/` (bistek, fort, giassi standalone)
- **JSONL Files**: Deprecated in favor of Parquet
- **Proprietary References**: Removed all Indicium company references

### Fixed
- **Empty Struct Serialization**: Fixed Parquet writer to handle empty nested dicts
- **Windows UTF-8**: Documented environment variable configuration
- **DBT Wrapper Scripts**: Removed in favor of environment variable approach

---

## [1.0.0] - 2025-12-15

### Initial Release

#### Added
- Basic VTEX scraper for Bistek, Fort, Giassi
- JSONL storage format
- DuckDB analytics engine
- Streamlit dashboard
- GitHub Actions for automated scraping

#### Known Issues
- Large JSONL files (11GB+)
- Slow queries (60+ seconds)
- No data quality enforcement
- Silent exceptions in error handling
- Manual UTF-8 configuration required

---

## [0.1.0] - 2025-10-01

### Pre-release

#### Added
- Proof of concept scraper for Bistek
- Manual Parquet conversion
- Basic analytics queries

---

## Version Format

- **MAJOR**: Breaking changes (incompatible API/schema changes)
- **MINOR**: New features (backwards-compatible)
- **PATCH**: Bug fixes (backwards-compatible)

---

## Links

- [GitHub Releases](https://github.com/alanludke/market-scraper/releases)
- [Project Repository](https://github.com/alanludke/market-scraper)
- [Documentation](docs/)

---

<div align="center">

[← Back to README](README.md)

</div>
