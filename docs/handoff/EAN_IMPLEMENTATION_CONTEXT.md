# Contexto de Implementação - Base de EANs (OpenFoodFacts)

**Data:** 2026-02-06
**Status:** ✅ Implementação completa, enriquecimento em execução

---

## 🎯 O que foi implementado

### 1. Arquitetura Separada (src/enrichment/openfoodfacts/)

Nova estrutura criada seguindo **Opção B** (separação de responsabilidades):

```
src/enrichment/openfoodfacts/
├── enricher.py      # Pipeline completo de enriquecimento
├── watermark.py     # Tracking incremental (evita re-fetch)
└── __init__.py      # Exports

src/schemas/
└── openfoodfacts.py # Pydantic validation (Nutriscore, EAN, nutriments)

cli_enrich.py        # CLI amigável com progress bar
```

**Decisões arquiteturais:**
- ❌ Não herda de `BaseScraper` (scraper VTEX é regional, OFF é global lookup)
- ✅ Pipeline standalone especializado
- ✅ Rate limiting: 10 req/s (600/min)
- ✅ Partitioning: `data/bronze/supermarket=openfoodfacts/region=global/`

### 2. Integração DBT Completa

**Modelos criados:**
- ✅ `stg_openfoodfacts__products.sql` - Staging (ephemeral)
- ✅ `dim_ean.sql` - Dimensão conformed (21.257 EANs)
- ✅ `schema.yml` - Documentação completa

**Modelos modificados:**
- ✅ `fct_daily_prices.sql` - Adicionado `ean_key` FK
- ✅ `sources.yml` - Adicionado `bronze_openfoodfacts`
- ✅ `source_parquet.sql` - Adicionado caminho para OFF

**Testes:**
- ✅ 12/12 testes passando
- ✅ Referential integrity: `fct_daily_prices.ean_key → dim_ean.ean_key`
- ✅ Uniqueness, not_null, accepted_values

### 3. Dados e Validação

**Teste inicial (100 EANs):**
- ✅ Extração: 20.250 EANs únicos do `tru_product`
- ✅ API: 7 produtos encontrados (7% - esperado para produtos BR)
- ✅ Bronze: Parquet salvo corretamente
- ✅ Watermark: Funcionando

**DBT:**
- ✅ `dim_ean` compilado e criado (21.257 rows)
- ✅ `fct_daily_prices` atualizado com `ean_key`
- ✅ Todos os testes passando

---

## 🔄 Estado Atual (IMPORTANTE!)

### Enriquecimento em Execução

**Comando executado:**
```bash
python cli_enrich.py eans --full
```

**Detalhes:**
- **Iniciado:** 11:03:59 (06/02/2026)
- **EANs:** 20.250 EANs
- **Rate:** 10 req/s = 600 req/min
- **Tempo estimado:** ~34 minutos
- **Término previsto:** ~11:38
- **PID:** 23028
- **Output file:** `C:\Users\ALAN~1.LUD\AppData\Local\Temp\claude\c--Users-alan-ludke-indicium-Documents-market-scraper\tasks\b23621f.output`

### Como verificar se terminou

```bash
# 1. Verificar se processo está rodando
tasklist | findstr "23028"

# 2. Ver output/estatísticas finais
tail "C:\Users\ALAN~1.LUD\AppData\Local\Temp\claude\c--Users-alan-ludke-indicium-Documents-market-scraper\tasks\b23621f.output"

# 3. Verificar se Parquet foi criado
ls "data/bronze/supermarket=openfoodfacts/region=global/year=2026/month=02/day=06/"
```

---

## 📋 Próximos Passos (Quando terminar)

### 1. Verificar resultado do enriquecimento

```bash
tail "C:\Users\ALAN~1.LUD\AppData\Local\Temp\claude\c--Users-alan-ludke-indicium-Documents-market-scraper\tasks\b23621f.output"
```

Esperado:
```
==================================================
ENRICHMENT STATISTICS
==================================================
Total EANs extracted:    20250
EANs fetched from API:   20250
Products found:          ~XXXX (esperado: 5-10% = 1.000-2.000)
Products not found:      ~XXXX
Success rate:            ~X.X%
==================================================
```

### 2. Atualizar dim_ean no DBT

```bash
cd src/transform/dbt_project

# Rodar dim_ean (incorpora novos dados do bronze)
dbt run --select dim_ean

# Atualizar fct_daily_prices
dbt run --select fct_daily_prices

# Testar integridade
dbt test --select dim_ean fct_daily_prices
```

### 3. Validar coverage de enriquecimento

```bash
# Via Python
python -c "import duckdb; conn = duckdb.connect('data/analytics.duckdb', read_only=True); print(conn.execute('SELECT COUNT(*) as total_eans, SUM(CASE WHEN is_enriched THEN 1 ELSE 0 END) as enriched_count, ROUND(100.0 * SUM(CASE WHEN is_enriched THEN 1 ELSE 0 END) / COUNT(*), 2) as enrichment_pct FROM dev_local.dim_ean').fetchdf())"

# Esperado: 5-10% de coverage (produtos brasileiros têm menor presença no OFF)
```

### 4. Análises possíveis

```sql
-- Top 10 produtos enriquecidos
SELECT
    ean_code,
    canonical_name,
    canonical_brand,
    nutriscore_grade,
    nutrition_quality
FROM dev_local.dim_ean
WHERE is_enriched = true
LIMIT 10;

-- Distribuição de Nutriscore
SELECT
    nutriscore_grade,
    nutrition_quality,
    COUNT(*) as product_count
FROM dev_local.dim_ean
WHERE is_enriched = true
GROUP BY nutriscore_grade, nutrition_quality
ORDER BY nutriscore_grade;

-- Produtos com EAN mas sem enriquecimento
SELECT COUNT(*) as not_enriched_count
FROM dev_local.dim_ean
WHERE is_enriched = false;
```

---

## 📁 Arquivos Criados/Modificados

### Novos Arquivos

**Enriquecimento:**
- `src/enrichment/__init__.py`
- `src/enrichment/openfoodfacts/__init__.py`
- `src/enrichment/openfoodfacts/enricher.py` (300+ LOC)
- `src/enrichment/openfoodfacts/watermark.py` (80 LOC)
- `src/schemas/openfoodfacts.py` (90 LOC)
- `cli_enrich.py` (150 LOC)

**DBT:**
- `src/transform/dbt_project/models/staging/stg_openfoodfacts__products.sql`
- `src/transform/dbt_project/models/marts/conformed/dim_ean.sql`
- `src/transform/dbt_project/models/marts/conformed/schema.yml`

### Arquivos Modificados

**DBT:**
- `src/transform/dbt_project/models/staging/sources.yml` (adicionado bronze_openfoodfacts)
- `src/transform/dbt_project/macros/source_parquet.sql` (adicionado path OFF)
- `src/transform/dbt_project/models/marts/pricing_marts/fct_daily_prices.sql` (adicionado ean_key)
- `src/transform/dbt_project/models/marts/pricing_marts/schema.yml` (documentado ean_key)

---

## 🔧 Comandos Úteis

### CLI de Enriquecimento

```bash
# Ver estatísticas do watermark
python cli_enrich.py stats

# Enriquecimento incremental (só novos EANs)
python cli_enrich.py eans

# Enriquecimento completo (re-fetch todos)
python cli_enrich.py eans --full

# Teste com limite
python cli_enrich.py eans --limit 100

# Com verbose logging
python cli_enrich.py eans --verbose
```

### DBT

```bash
cd src/transform/dbt_project

# Compilar (verifica sintaxe)
dbt compile --select dim_ean

# Rodar modelos
dbt run --select dim_ean
dbt run --select dim_ean+  # dim_ean + downstream

# Testar
dbt test --select dim_ean
dbt test --select dim_ean fct_daily_prices

# Gerar docs
dbt docs generate
dbt docs serve
```

---

## 📊 KPIs Desbloqueados

Com a base de EANs implementada, agora é possível:

### 1. Price-per-kg Normalization
```sql
-- Exemplo: Calcular preço por kg usando net_weight
SELECT
    p.product_name,
    p.min_price,
    e.net_weight,
    -- Parsing net_weight (ex: "500g" → 0.5kg)
    -- Cálculo: min_price / peso_kg
FROM dev_local.fct_daily_prices p
JOIN dev_local.dim_ean e ON p.ean_key = e.ean_key
WHERE e.net_weight IS NOT NULL;
```

### 2. Nutritional Value Analysis
```sql
-- Top 10 produtos com melhor custo-benefício nutricional
SELECT
    e.canonical_name,
    e.canonical_brand,
    e.nutriscore_grade,
    AVG(p.min_price) as avg_price
FROM dev_local.fct_daily_prices p
JOIN dev_local.dim_ean e ON p.ean_key = e.ean_key
WHERE e.nutriscore_grade IN ('a', 'b')  -- Excelente nutrição
GROUP BY e.canonical_name, e.canonical_brand, e.nutriscore_grade
ORDER BY avg_price ASC
LIMIT 10;
```

### 3. Product Deduplication (Cross-Store)
```sql
-- Mesmo produto (EAN) vendido em diferentes lojas
SELECT
    e.ean_code,
    e.canonical_name,
    s.store_name,
    p.min_price
FROM dev_local.fct_daily_prices p
JOIN dev_local.dim_ean e ON p.ean_key = e.ean_key
JOIN dev_local.dim_store s ON p.store_key = s.store_key
WHERE e.ean_code = '7891234567890'  -- Exemplo
ORDER BY p.min_price ASC;
```

### 4. Enrichment Coverage Monitoring
```sql
-- Coverage por loja
SELECT
    s.store_name,
    COUNT(DISTINCT p.ean_key) as total_eans,
    SUM(CASE WHEN e.is_enriched THEN 1 ELSE 0 END) as enriched_count,
    ROUND(100.0 * SUM(CASE WHEN e.is_enriched THEN 1 ELSE 0 END) / COUNT(*), 2) as coverage_pct
FROM dev_local.fct_daily_prices p
JOIN dev_local.dim_store s ON p.store_key = s.store_key
LEFT JOIN dev_local.dim_ean e ON p.ean_key = e.ean_key
GROUP BY s.store_name;
```

---

## ⚠️ Pontos de Atenção

### 1. Coverage Esperado
- OpenFoodFacts tem **mais produtos internacionais** que brasileiros
- Coverage esperado: **5-15%** para produtos brasileiros
- Produtos importados terão coverage maior (~50-70%)

### 2. Watermark Management
- Watermark em: `data/metadata/ean_enrichment_watermark.json`
- Contém lista de EANs já processados (mesmo que não encontrados)
- Para re-processar: usar `--full` ou deletar watermark

### 3. Incremental Updates
- Rodar `python cli_enrich.py eans` após novos scrapes VTEX
- Pipeline detecta novos EANs automaticamente
- Recomendado: rodar semanalmente

### 4. Performance
- 10 req/s = limite respeitoso do OpenFoodFacts
- 20K EANs = ~35 minutos
- Para volumes maiores: considerar bulk CSV download

---

## 🚀 Futuro - Bulk CSV Download

**Quando implementar:**
- Volume > 100K EANs
- Re-fetch completo frequente
- Coverage baixo (precisa tentar mais EANs)

**Como:**
1. Download: `https://world.openfoodfacts.org/data`
2. Parse CSV → Parquet
3. Load para bronze (substituir API calls)
4. Update semanal/mensal

**Vantagens:**
- Muito mais rápido (minutos vs horas)
- Sem rate limiting
- Dataset completo (~3M produtos)

**Desvantagens:**
- Arquivo grande (~600MB comprimido)
- Precisa parsing CSV
- Update menos frequente

---

## 📞 Troubleshooting

### "No new EANs to enrich"
**Causa:** Watermark já contém todos os EANs
**Solução:** Usar `--full` para re-processar

### "DuckDB file locked"
**Causa:** Outro processo usando analytics.duckdb
**Solução:** Fechar notebooks/scripts Python, matar processo

### "Low enrichment coverage (<5%)"
**Esperado:** Produtos brasileiros têm menor presença no OFF
**Solução:** Considerar fontes adicionais (GS1 Brazil, scraping próprio)

### "API timeout/errors"
**Causa:** OpenFoodFacts API instável
**Solução:** Re-rodar (watermark evita duplicação), tentar em horário diferente

---

## ✅ Checklist de Validação Final

Quando o enriquecimento terminar:

- [ ] Verificar estatísticas no output (produtos encontrados, success rate)
- [ ] Confirmar Parquet criado em `data/bronze/supermarket=openfoodfacts/`
- [ ] Rodar `dbt run --select dim_ean`
- [ ] Rodar `dbt test --select dim_ean fct_daily_prices`
- [ ] Verificar coverage (query acima)
- [ ] Validar sample de produtos enriquecidos (query acima)
- [ ] Atualizar `NEXT_AGENT_INSTRUCTIONS.md` (marcar Tarefa 2 completa)
- [ ] Documentar findings (coverage real, produtos encontrados, etc.)

---

**Última atualização:** 2026-02-06 11:10
**Próxima ação:** Verificar se enriquecimento terminou (~11:38)
**Responsável:** Alan Ludke
**Claude Agent:** Sonnet 4.5
