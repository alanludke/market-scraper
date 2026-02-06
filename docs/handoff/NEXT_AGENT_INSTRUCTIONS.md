# Instruções para Próximo Agente Claude
**Handoff de Trabalho - Market Scraper**

---

## 📋 Contexto Atual

O Market Scraper está em **Fase 2** de desenvolvimento. A modelagem dimensional Kimball foi completamente implementada (Fase 1), com:

✅ **Completo:**
- 5 dimensões conformed (dim_date, dim_store, dim_region, dim_brand, dim_product)
- Fact tables com surrogate keys (fct_daily_prices, fct_price_comparison_v2)
- Snapshots DBT para SCD Type 2 (histórico de preços)
- Testes de referential integrity (18/18 passando)
- Schema VTEX expandido (Promotions, isVariantOf)
- Modelos DBT de análise de promoções (fct_active_promotions, fct_promotion_summary)
- Dashboard Streamlit (3 páginas: Preços, Promoções, Competitividade)

---

## 🎯 Tarefas Pendentes (em ordem de prioridade)

### Tarefa 1: Finalizar Dashboard Streamlit ⭐ (1-2 dias)

**Status:** 70% completo

**O que falta:**
1. **Testar o dashboard localmente**
   ```bash
   cd c:\Users\alan.ludke_indicium\Documents\market_scraper
   pip install -r requirements_dashboard.txt
   streamlit run src/dashboard/app.py
   ```

2. **Adicionar página de Disponibilidade** (opcional, mas útil)
   - Criar `src/dashboard/pages/4_📦_Disponibilidade.py`
   - Visualizar produtos out of stock
   - Low inventory alerts
   - Disponibilidade por região

3. **Melhorias de UX:**
   - Adicionar filtros de data (se houver mais de 1 dia de dados)
   - Adicionar download de dados (CSV/Excel)
   - Adicionar cache de queries lentas

**Arquivos relevantes:**
- `src/dashboard/app.py` (página principal)
- `src/dashboard/pages/1_💰_Análise_de_Preços.py`
- `src/dashboard/pages/2_🏷️_Análise_de_Promoções.py`
- `src/dashboard/pages/3_🥊_Competitividade.py`

---

### Tarefa 2: Implementar Base de EANs (OpenFoodFacts) ⭐⭐ (2-3 semanas)

**Status:** 0% (não iniciado)

**Objetivo:** Integrar base de dados global de EANs para deduplicação e enriquecimento de produtos.

**Passos:**

1. **Criar scraper OpenFoodFacts**
   ```python
   # Localização: src/ingest/scrapers/openfoodfacts_scraper.py

   import requests

   class OpenFoodFactsScraper:
       """Fetch product data from OpenFoodFacts API."""

       BASE_URL = "https://world.openfoodfacts.org/api/v0"

       def get_product_by_ean(self, ean: str):
           """
           Fetch product by EAN code.

           Example:
               GET https://world.openfoodfacts.org/api/v0/product/7891000100103.json
           """
           url = f"{self.BASE_URL}/product/{ean}.json"
           response = requests.get(url)

           if response.status_code == 200:
               data = response.json()
               if data.get('status') == 1:  # Product found
                   return data.get('product')
           return None

       def batch_enrich_eans(self, eans: list):
           """Enrich multiple EANs (with rate limiting)."""
           # Rate limit: Max 10 requests/second (be respectful!)
           # Implementation: Loop through EANs, fetch, save to bronze/
   ```

2. **Extrair EANs dos produtos VTEX existentes**
   ```sql
   -- Query DBT para extrair EANs únicos do bronze
   -- Localização: src/transform/dbt_project/analyses/extract_unique_eans.sql

   SELECT DISTINCT
       ean
   FROM (
       SELECT
           unnest(eans) as ean
       FROM {{ ref('tru_product') }}
       WHERE eans IS NOT NULL
   )
   WHERE ean IS NOT NULL
       AND length(ean) IN (8, 13, 14)  -- Valid EAN lengths
   ```

3. **Criar schema Pydantic para OpenFoodFacts**
   ```python
   # Localização: src/schemas/openfoodfacts.py

   from pydantic import BaseModel, Field
   from typing import Optional, List, Dict, Any

   class OpenFoodFactsNutriments(BaseModel):
       """Nutritional information."""
       energy_100g: Optional[float] = Field(None, alias='energy-kcal_100g')
       proteins_100g: Optional[float] = None
       fat_100g: Optional[float] = None
       carbohydrates_100g: Optional[float] = None
       sugars_100g: Optional[float] = None
       fiber_100g: Optional[float] = None
       salt_100g: Optional[float] = None

   class OpenFoodFactsProduct(BaseModel):
       """OpenFoodFacts product schema."""
       code: str  # EAN barcode
       product_name: Optional[str] = None
       brands: Optional[str] = None
       categories: Optional[str] = None
       countries: Optional[str] = None
       quantity: Optional[str] = None
       nutriscore_grade: Optional[str] = None  # A-E rating
       nutriments: Optional[OpenFoodFactsNutriments] = None

       class Config:
           extra = "allow"
   ```

4. **Criar modelos DBT para dim_ean**
   ```sql
   -- Localização: src/transform/dbt_project/models/marts/conformed/dim_ean.sql

   {{
       config(
           materialized='table',
           tags=['conformed', 'dimension', 'ean']
       )
   }}

   with
       eans_from_vtex as (
           select distinct
               unnest(eans) as ean_code
           from {{ ref('tru_product') }}
           where eans is not null
       )

       , openfoodfacts_enrichment as (
           select
               code as ean_code,
               product_name as canonical_name,
               brands as canonical_brand,
               categories,
               quantity as net_weight,
               countries as country_of_origin,
               nutriscore_grade,
               nutriments
           from {{ source('bronze_openfoodfacts', 'products') }}
       )

       , ean_master as (
           select
               v.ean_code,
               coalesce(o.canonical_name, 'Unknown') as product_name,
               coalesce(o.canonical_brand, 'Unknown') as brand,
               o.categories,
               o.net_weight,
               o.country_of_origin,
               o.nutriscore_grade,
               case
                   when o.nutriscore_grade in ('a', 'b') then 'Excellent'
                   when o.nutriscore_grade = 'c' then 'Good'
                   when o.nutriscore_grade = 'd' then 'Fair'
                   when o.nutriscore_grade = 'e' then 'Poor'
                   else 'Unknown'
               end as nutrition_quality
           from eans_from_vtex v
           left join openfoodfacts_enrichment o
               on v.ean_code = o.ean_code
       )

       , with_surrogate_key as (
           select
               row_number() over (order by ean_code) as ean_key,
               ean_code,
               product_name,
               brand,
               categories,
               net_weight,
               country_of_origin,
               nutriscore_grade,
               nutrition_quality
           from ean_master
       )

   select * from with_surrogate_key
   ```

5. **Atualizar fct_daily_prices para usar dim_ean**
   ```sql
   -- Adicionar FK ean_key em fct_daily_prices
   -- Permitir joins com dim_ean para análises nutricionais
   ```

**Recursos:**
- Documentação API: https://wiki.openfoodfacts.org/API/Read/Product
- Dataset completo: https://world.openfoodfacts.org/data (pode baixar CSV para bulk load)
- Rate limits: 10 requests/second (seja respeitoso!)

**KPIs Desbloqueados:**
- Price-per-gram comparison (R$/kg normalization)
- Nutritional value vs price correlation
- Organic premium analysis
- Cross-store product matching (mesmo EAN, nomes diferentes)

---

### Tarefa 3: Scraper de Concorrentes (Carrefour) ⭐ (3-4 semanas)

**Status:** 0% (não iniciado)

**Objetivo:** Adicionar scraper para Carrefour (também usa VTEX) e permitir competitive benchmarking.

**Passos:**

1. **Reusar VTEXScraper existente**
   - Carrefour também usa VTEX platform
   - Endpoint: `https://www.carrefour.com.br/api/catalog_system/pub/products/search`
   - Apenas configurar novo store config em `config/stores.yaml`

2. **Configurar novo source no DBT**
   ```yaml
   # src/transform/dbt_project/models/staging/sources.yml

   - name: bronze_carrefour
     description: Bronze layer data from Carrefour
     tables:
       - name: products
         external:
           location: '../../../../data/bronze/supermarket=carrefour/**/*.parquet'
   ```

3. **Atualizar staging model**
   ```sql
   -- src/transform/dbt_project/models/staging/stg_vtex__products.sql
   -- Adicionar UNION ALL com bronze_carrefour
   ```

4. **Criar fct_competitive_pricing**
   ```sql
   -- Compare preços VTEX stores (bistek, fort, giassi) vs Carrefour
   -- Join via ean_code (dim_ean)
   ```

**Recursos:**
- Carrefour usa mesma API VTEX que Bistek/Fort/Giassi
- Pode reusar 100% do código existente
- Apenas adicionar configuração em `config/`

---

### Tarefa 4: Automação de Scrapes Diários ⭐ (2-3 dias)

**Status:** 0% (não iniciado)

**Objetivo:** Configurar scrapes automáticos diários via cron (local) ou GitHub Actions (cloud).

**Opção A: Cron (Local)**
```bash
# Adicionar ao crontab (Linux/Mac) ou Task Scheduler (Windows)

# Executar scrape diário às 2h da manhã
0 2 * * * cd /path/to/market_scraper && python cli_ingest.py scrape --all

# Executar transformação DBT às 3h (após scrape)
0 3 * * * cd /path/to/market_scraper/src/transform/dbt_project && dbt run && dbt snapshot
```

**Opção B: GitHub Actions (Recomendado)**
```yaml
# .github/workflows/daily_scrape.yml

name: Daily Scrape & Transform

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:  # Allow manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scrapers
        run: python cli_ingest.py scrape --all

      - name: Upload to Azure Blob
        run: python cli_sync.py upload --layer bronze
        env:
          AZURE_STORAGE_CONNECTION_STRING: ${{ secrets.AZURE_CONNECTION }}

  transform:
    needs: scrape
    runs-on: ubuntu-latest
    steps:
      - name: Run DBT transformations
        run: |
          cd src/transform/dbt_project
          dbt run
          dbt snapshot
          dbt test
```

---

## 📂 Arquivos Importantes para Revisão

### Modelagem DBT
- `src/transform/dbt_project/models/marts/conformed/` - Dimensões
- `src/transform/dbt_project/models/marts/pricing_marts/` - Fact tables de preços
- `src/transform/dbt_project/snapshots/snap_product_prices.sql` - SCD Type 2

### Schemas Pydantic
- `src/schemas/vtex.py` - Schema VTEX (expandido com Promotions)
- `src/ingest/scrapers/vtex_scraper.py` - Scraper VTEX unificado

### Documentação Estratégica
- `docs/strategy/DATA_SOURCES_ROADMAP.md` - Roadmap de fontes de dados (EANs, concorrentes, reviews)
- `docs/architecture/DATA_LAYERS.md` - Arquitetura medallion (bronze → silver → gold)
- `docs/architecture/SNAPSHOTS.md` - Guia de SCD Type 2

### Dashboard
- `src/dashboard/app.py` - Aplicação Streamlit principal
- `src/dashboard/pages/` - Páginas de análise

---

## 🔧 Comandos Úteis

### Executar DBT
```bash
cd src/transform/dbt_project

# Run all models
dbt run

# Run snapshots (SCD Type 2)
dbt snapshot

# Run tests
dbt test

# Generate docs
dbt docs generate && dbt docs serve
```

### Executar Dashboard
```bash
streamlit run src/dashboard/app.py
```

### Executar Scrapers
```bash
# Scrape single store
python cli_ingest.py scrape bistek --limit 1000

# Scrape all stores
python cli_ingest.py scrape --all
```

---

## 📊 Estado Atual do Banco de Dados

**Localização:** `data/analytics.duckdb`

**Schemas:**
- `dev_local`: Desenvolvimento (onde estão as tabelas atuais)
- `snapshots`: Snapshots DBT (histórico de preços)

**Tabelas Principais:**
- `tru_product` (278.628 produtos)
- `dim_date` (767 datas)
- `dim_store` (3 lojas)
- `dim_region` (31 regiões)
- `dim_brand` (2.914 marcas)
- `dim_product` (29.385 produtos únicos)
- `fct_daily_prices` (278.628 registros)
- `fct_active_promotions` (54.106 promoções)
- `fct_price_comparison_v2` (2.452 comparações)
- `snap_product_prices` (278.628 snapshots iniciais)

---

## ✅ Checklist de Validação

Antes de considerar cada tarefa completa, validar:

### Dashboard
- [ ] Dashboard abre sem erros
- [ ] Todas as 3 páginas carregam dados corretamente
- [ ] Filtros funcionam (lojas, marcas)
- [ ] Gráficos renderizam corretamente
- [ ] Performance aceitável (<5s para carregar página)

### Base de EANs
- [ ] OpenFoodFacts API funciona (testar com EANs reais)
- [ ] Schema Pydantic valida respostas corretamente
- [ ] dim_ean criada com surrogate keys
- [ ] fct_daily_prices tem FK para dim_ean
- [ ] Testes de referential integrity passam

### Scraper Carrefour
- [ ] Scraper coleta produtos sem erros
- [ ] Dados salvos em bronze/supermarket=carrefour/
- [ ] DBT processa Carrefour junto com outras lojas
- [ ] fct_competitive_pricing criado
- [ ] Dashboard mostra dados de Carrefour

### Automação
- [ ] Cron/GitHub Actions configurado
- [ ] Scrape executa sem intervenção manual
- [ ] DBT run executa após scrape
- [ ] Dados sincronizados para Azure Blob (opcional)

---

## 🆘 Troubleshooting Comum

**Problema:** DBT models não compilam
- **Solução:** `cd src/transform/dbt_project && dbt parse --debug`
- Verificar logs em `logs/dbt.log`

**Problema:** Dashboard não conecta ao DuckDB
- **Solução:** Verificar caminho do banco: `data/analytics.duckdb` existe?
- Testar conexão: `python -c "import duckdb; duckdb.connect('data/analytics.duckdb')"`

**Problema:** Scraper VTEX falha
- **Solução:** Verificar logs em `data/logs/app.log`
- Verificar metrics: `data/metrics/runs.duckdb`

---

## 📞 Próximos Passos Sugeridos

1. **Testar dashboard** (30 min) - Garantir que tudo funciona
2. **Implementar EANs** (2-3 semanas) - Alto ROI, habilita deduplicação
3. **Scraper Carrefour** (3-4 semanas) - Competitive intelligence
4. **Automação** (2-3 dias) - Dados sempre frescos

---

**Última atualização:** 2026-02-06
**Autor:** Claude Sonnet 4.5
**Próximo agente:** Boa sorte! 🚀
