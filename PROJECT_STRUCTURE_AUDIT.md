# Complete Project Structure Audit

**Date**: 2026-02-08
**Purpose**: Categorize every file and directory, identify what needs to move

---

## 📊 Current Structure (Tree View)

```
market_scraper/
├── 📁 ROOT LEVEL
│   ├── .devcontainer/          ✅ KEEP (Dev environment config)
│   ├── .git/                   ✅ KEEP (Version control)
│   ├── .github/                ✅ KEEP (CI/CD workflows)
│   ├── .gitignore              ✅ KEEP (Repository-level)
│   ├── .pytest_cache/          ❌ DELETE (Generated, should be in .gitignore)
│   ├── __pycache__/            ❌ DELETE (Generated, should be in .gitignore)
│   ├── htmlcov/                🔧 MOVE → tests/htmlcov/ (Test coverage reports)
│   │
│   ├── archive/                ⏳ TO DELETE (After data migration)
│   ├── data/                   ✅ KEEP (Data storage, gitignored)
│   │
│   ├── docs/                   ✅ KEEP (Project documentation)
│   │   ├── architecture/       ✅
│   │   ├── deployment/         ✅
│   │   ├── development/        ✅
│   │   ├── features/           ✅
│   │   ├── handoff/            ✅
│   │   ├── operations/         ✅
│   │   ├── quality/            ✅
│   │   ├── reports/            ✅
│   │   ├── strategy/           ✅
│   │   └── templates/          ✅
│   │
│   ├── scripts/                ✅ KEEP (Utility scripts)
│   │   ├── azure/              ✅
│   │   ├── deployment/         ✅
│   │   ├── maintenance/        ✅
│   │   ├── monitoring/         ✅
│   │   └── setup/              ✅
│   │
│   ├── src/                    ✅ KEEP (Source code)
│   │   ├── analytics/          ✅
│   │   ├── cli/                ✅
│   │   ├── dashboard/          ✅
│   │   │   ├── .streamlit/     ✅ (Colocated)
│   │   │   └── pages/          ✅ (Colocated)
│   │   ├── enrichment/         ✅
│   │   ├── ingest/             ✅
│   │   │   └── config/         ✅ (Colocated)
│   │   ├── observability/      ✅
│   │   │   └── logs/           ✅ (Colocated)
│   │   ├── orchestration/      ✅
│   │   │   ├── .prefectignore  ✅ (Colocated)
│   │   │   └── prefect.yaml    ✅ (Colocated)
│   │   ├── schemas/            ✅
│   │   ├── scrapers/           ❓ MAYBE DUPLICATE? (Check vs src/ingest/scrapers/)
│   │   ├── storage/            ✅
│   │   └── transform/          ✅
│   │
│   ├── tests/                  ✅ KEEP (Test suite)
│   │   ├── pytest.ini          ✅ (Colocated)
│   │   ├── fixtures/           ✅
│   │   ├── integration/        ✅
│   │   └── unit/               ✅
│   │
│   ├── CHANGELOG.md            ✅ KEEP (Repository-level)
│   ├── CLAUDE.md               ✅ KEEP (Project instructions)
│   ├── COLOCATION_COMPLETE.md  ✅ KEEP (Documentation)
│   ├── CONTRIBUTING.md         ✅ KEEP (Repository-level)
│   ├── CONTRIBUTORS.md         ✅ KEEP (Repository-level)
│   ├── Dockerfile              ✅ KEEP (Container definition)
│   ├── LICENSE                 ✅ KEEP (Repository-level)
│   ├── market_data.duckdb      ❓ WHAT IS THIS? (Should be in data/?)
│   ├── README.md               ✅ KEEP (Repository-level)
│   ├── REORGANIZATION_SUMMARY.md ✅ KEEP (Documentation)
│   ├── requirements.txt        ✅ KEEP (Repository-level)
│   ├── RESTRUCTURE_PLAN.md     ✅ KEEP (Documentation)
│   └── SETUP.md                ✅ KEEP (Repository-level)
```

---

## 🚨 Issues Identified

### 1. Generated Files in Root (Should be Gitignored)
```
❌ .pytest_cache/    → Should be gitignored
❌ __pycache__/      → Should be gitignored
❌ htmlcov/          → Should be in tests/ and gitignored
```

**Action**:
- Add to `.gitignore`
- Move `htmlcov/` to `tests/htmlcov/` (coverage reports belong with tests)
- Delete `.pytest_cache/` and `__pycache__/` from root

### 2. Database File in Root
```
❓ market_data.duckdb  → Should this be in data/?
```

**Questions**:
- Is this tracked in Git? (Check if it's a dev database)
- Should it be in `data/` instead?
- Should it be gitignored?

### 3. Potential Duplicate Directory
```
❓ src/scrapers/  vs  src/ingest/scrapers/
```

**Question**: Are these the same? If yes, delete `src/scrapers/` (keep `src/ingest/scrapers/`)

---

## 🎯 Recommended Actions

### Action 1: Move Coverage Reports
```bash
# Create tests/htmlcov/ directory
mkdir -p tests/coverage

# Move htmlcov to tests
mv htmlcov tests/htmlcov

# Update .coveragerc or pytest.ini to output to tests/htmlcov/
```

### Action 2: Update .gitignore
```gitignore
# Generated files (should NOT be in repo)
__pycache__/
.pytest_cache/
*.pyc
*.pyo
*.pyd

# Test coverage
htmlcov/
tests/htmlcov/
.coverage
.coverage.*

# DuckDB files (if they're dev databases)
*.duckdb
*.duckdb.wal
```

### Action 3: Clean Up Generated Files
```bash
# Delete generated files from root
rm -rf .pytest_cache/
rm -rf __pycache__/

# Clean up all __pycache__ in project
find . -type d -name "__pycache__" -exec rm -rf {} +
```

### Action 4: Investigate Duplicates
```bash
# Check if src/scrapers/ is duplicate
ls -la src/scrapers/
ls -la src/ingest/scrapers/

# If duplicate, delete src/scrapers/
rm -rf src/scrapers/
```

### Action 5: Move DuckDB File (if needed)
```bash
# If market_data.duckdb is a dev database
mv market_data.duckdb data/market_data.duckdb

# Update references in code
grep -r "market_data.duckdb" src/
```

---

## 📋 Final Clean Structure

After cleanup:

```
market_scraper/
├── .devcontainer/              # Dev environment
├── .git/                       # Version control
├── .github/                    # CI/CD workflows
├── .gitignore                  # Repository-level
│
├── archive/                    # ⏳ To delete after migration
├── data/                       # Data storage (gitignored)
│   └── market_data.duckdb      # 🔧 MOVED HERE
│
├── docs/                       # Documentation
│
├── scripts/                    # Utility scripts
│   ├── azure/
│   ├── deployment/
│   ├── maintenance/
│   ├── monitoring/
│   └── setup/
│
├── src/                        # Source code
│   ├── analytics/
│   ├── cli/
│   ├── dashboard/
│   │   ├── .streamlit/         # Colocated config
│   │   └── pages/              # Colocated pages
│   ├── enrichment/
│   ├── ingest/
│   │   ├── config/             # Colocated config
│   │   └── scrapers/           # Keep this one
│   ├── observability/
│   │   └── logs/               # Colocated logs
│   ├── orchestration/
│   │   ├── .prefectignore      # Colocated config
│   │   └── prefect.yaml        # Colocated config
│   ├── schemas/
│   ├── storage/
│   └── transform/
│
├── tests/                      # Test suite
│   ├── pytest.ini              # Colocated config
│   ├── htmlcov/                # 🔧 MOVED HERE (coverage reports)
│   ├── fixtures/
│   ├── integration/
│   └── unit/
│
├── CHANGELOG.md                # Repository docs
├── CLAUDE.md
├── CONTRIBUTING.md
├── CONTRIBUTORS.md
├── Dockerfile
├── LICENSE
├── README.md
├── requirements.txt
└── SETUP.md
```

---

## 🎯 Categorization Summary

### ✅ Repository-Level (Stay at Root)
- `.devcontainer/`, `.git/`, `.github/`
- `.gitignore`, `Dockerfile`, `requirements.txt`
- `README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SETUP.md`

### ✅ Colocated (Already in Right Place)
- `src/dashboard/.streamlit/`, `src/dashboard/pages/`
- `src/ingest/config/`
- `src/observability/logs/`
- `src/orchestration/prefect.yaml`, `src/orchestration/.prefectignore`
- `tests/pytest.ini`

### 🔧 Need to Move
- `htmlcov/` → `tests/htmlcov/`
- `market_data.duckdb` → `data/market_data.duckdb` (if it's a dev DB)

### ❌ Need to Delete
- `.pytest_cache/` (generated)
- `__pycache__/` (generated)
- `archive/` (after data migration)
- `src/scrapers/` (if duplicate of `src/ingest/scrapers/`)

### 📝 Need to Update
- `.gitignore` (add generated files)
- `.coveragerc` or `pytest.ini` (output to `tests/htmlcov/`)

---

## 🚀 Execution Script

Create `scripts/final_cleanup.py`:

```python
"""
Final cleanup script.

Actions:
1. Move htmlcov/ to tests/htmlcov/
2. Delete .pytest_cache/ and __pycache__/
3. Check for src/scrapers/ duplicate
4. Move market_data.duckdb to data/ (if exists)
5. Update .gitignore
"""
```

---

## ✅ Quality Checklist

After cleanup:

- [ ] No `__pycache__/` in root
- [ ] No `.pytest_cache/` in root
- [ ] Coverage reports in `tests/htmlcov/`
- [ ] All configs colocated with their domains
- [ ] `.gitignore` updated
- [ ] No duplicate directories
- [ ] All tests pass
- [ ] All imports work

---

## 📚 Colocation Principle Applied

| Domain | Config Files | Location |
|--------|--------------|----------|
| Dashboard | `.streamlit/`, `pages/` | `src/dashboard/` |
| Orchestration | `prefect.yaml`, `.prefectignore` | `src/orchestration/` |
| Ingestion | `config/stores.yaml` | `src/ingest/config/` |
| Observability | `logs/` | `src/observability/logs/` |
| Testing | `pytest.ini`, `htmlcov/` | `tests/` |

**Result**: Each domain is self-contained! 🎯
