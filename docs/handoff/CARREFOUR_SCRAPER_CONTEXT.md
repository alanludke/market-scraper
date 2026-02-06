# Carrefour Scraper - Session Context

**Date**: 2026-02-06
**Status**: ✅ HTML Scraper Working
**Last Commit**: `496dfd6` - "Feat: Carrefour HTML scraper (working solution for API 503 block)"

---

## 🎯 O Que Foi Feito

### 1. Investigação do Problema (API 503)
- **Problema**: API VTEX do Carrefour retorna 503 (Service Unavailable)
- **Endpoints bloqueados**:
  - `/api/checkout/pub/regions` → 503
  - `/api/catalog_system/pub/products/search` → 503
- **Causa provável**: WAF/CloudFlare protection bloqueando acesso programático
- **Tentativas**: Cookies de sessão, headers de navegador → sem sucesso

### 2. Solução Alternativa: HTML Scraping
✅ **Implementado**: `src/ingest/scrapers/carrefour_html.py`

**Como funciona**:
1. **Discovery**: Sitemap XMLs (`/sitemap/product-1.xml`, product-2.xml, etc.)
   - Encontrados: **62,769 produtos** no total
   - Parâmetro especial: `sitemap_start_index: 1` (Carrefour começa em 1, não 0)

2. **Scraping**: Páginas HTML individuais
   - **Fonte de dados**: JSON-LD (Schema.org structured data)
   - **Formato**: `<script type="application/ld+json">` com `@type: "Product"`

3. **Dados extraídos**:
   ```json
   {
     "productId": "4297679",
     "productName": "Água de Coco Ducoco 200ml",
     "brand": "Ducoco",
     "price": 1.93,
     "ean": "7896016601972",
     "availability": "InStock",
     "image": "https://..."
   }
   ```

4. **Validação**: Pydantic `VTEXProduct` schema (compatível com scrapers VTEX existentes)

### 3. Configuração

**Arquivo**: `config/stores.yaml`

```yaml
carrefour:
  platform: carrefour_html          # Scraper específico (não "vtex")
  base_url: "https://mercado.carrefour.com.br"
  sitemap_pattern: "/sitemap/product-{n}.xml"
  sitemap_start_index: 1            # IMPORTANTE: Começa em 1, não 0
  batch_size: 20                    # Menor que API (20 vs 50)
  request_delay: 0.5                # Respeitoso (0.5s vs 0.15s)
  max_workers: 1                    # Sem paralelização
  regions:
    florianopolis_centro:
      cep: "88010-000"
      sc: "1"
      hub_id: null
    # ... 4 outras regiões
```

### 4. Resultados dos Testes

**Teste 1: 10 produtos**
- ✅ 6 produtos scraped (60%)
- ❌ 4 produtos 404 (inativos)
- ✅ 0 erros de validação

**Teste 2: 100 produtos**
- ✅ **73 produtos scraped (73%)**
- ❌ 27 produtos 404 (inativos - normal)
- ✅ 1 erro de validação (produto com preço = 0)
- ⏱️ **Tempo: ~2.5 minutos**
- 📁 **Arquivo**: `data/bronze/supermarket=carrefour/region=florianopolis_centro/.../carrefour_florianopolis_centro_full.parquet`

**Qualidade dos dados**:
```
Product ID: 4297679
Name: Água de Coco Ducoco 200ml
Brand: Ducoco
Price: R$ 1.93
EAN: 7896016601972
```

---

## 📊 Estado Atual

### Arquivos Criados/Modificados

1. **Novo scraper**:
   - `src/ingest/scrapers/carrefour_html.py` (274 linhas)
   - Registrado em `src/ingest/scrapers/__init__.py`

2. **Configuração**:
   - `config/stores.yaml` - Carrefour com platform: "carrefour_html"

3. **Commits**:
   - `65a3e79` - Sitemap discovery (parâmetro `sitemap_start_index`)
   - `496dfd6` - HTML scraper funcionando

4. **Dados gerados** (testes):
   - `data/bronze/supermarket=carrefour/region=florianopolis_centro/year=2026/month=02/day=06/`
   - 73 produtos em Parquet

### Limitações Conhecidas

1. **Disponibilidade**: JSON-LD não tem cookie de região → mostra disponibilidade genérica
2. **List Price**: JSON-LD não tem preço de lista → `ListPrice = Price` (sem dados de promoção)
3. **404 Rate**: ~27% de produtos inativos (sitemap desatualizado)
4. **Performance**: ~0.5s por produto (vs API em batch)

### Próximos Passos (Pending)

#### 1. **Scrape Completo** (Opcional)
```bash
# Scrape todas as 5 regiões (~62k produtos)
python cli.py scrape carrefour --all

# Estimativa:
# - Tempo: ~9 horas (0.5s × 62,769 produtos)
# - Produtos esperados: ~45,821 (73% de 62,769)
# - Recomendação: Rodar overnight
```

#### 2. **DBT Source**
Adicionar Carrefour ao `src/transform/dbt_project/models/staging/sources.yml`:

```yaml
sources:
  - name: carrefour_bronze
    database: market_scraper
    schema: main
    tables:
      - name: carrefour_products
        description: "Carrefour product data from HTML scraping"
        meta:
          source_type: html_scraping
          api_blocked: true
        loaded_at_field: _metadata_scraped_at
```

#### 3. **DBT Staging Model**
Criar `src/transform/dbt_project/models/staging/stg_carrefour__products.sql`:

```sql
{{
    config(
        materialized='incremental',
        unique_key='product_id',
        on_schema_change='append_new_columns'
    )
}}

with source as (
    select * from {{ source_parquet('carrefour', 'carrefour_*_full.parquet') }}
)

-- Same transformation as other VTEX stores (bistek, fort, giassi)
-- ...
```

#### 4. **Dashboard**
Adicionar Carrefour aos filtros:
- `src/dashboard/pages/1_💰_Análise_de_Preços.py`
- `src/dashboard/pages/2_🏷️_Análise_de_Promoções.py`
- `src/dashboard/pages/3_🥊_Competitividade.py`

---

## 🔧 Comandos Úteis

### Scraping
```bash
# Teste com limite
python cli.py scrape carrefour --limit 100 --region florianopolis_centro

# Scrape completo (todas as regiões)
python cli.py scrape carrefour --all

# Região específica sem limite
python cli.py scrape carrefour --region florianopolis_trindade
```

### Verificar Dados
```python
import pandas as pd

# Ler Parquet gerado
df = pd.read_parquet('data/bronze/supermarket=carrefour/region=florianopolis_centro/year=2026/month=02/day=06/run_carrefour_20260206_112310/carrefour_florianopolis_centro_full.parquet')

print(f'Total: {len(df)} produtos')
print(df[['productId', 'productName', 'brand']].head())
```

### DBT (Após criar source)
```bash
cd src/transform/dbt_project

# Processar Carrefour no pipeline
dbt run --select stg_carrefour__products+

# Testar qualidade
dbt test --select stg_carrefour__products+
```

---

## 📝 Notas Técnicas

### Por Que HTML Scraping?
- ✅ **Funciona**: API bloqueada, HTML acessível
- ✅ **Dados completos**: JSON-LD tem todos os campos necessários
- ✅ **Compatível**: Output compatível com schema VTEX existente
- ⚠️ **Mais lento**: 0.5s/produto vs batches de 50 via API
- ⚠️ **Sem promoções**: JSON-LD não tem ListPrice diferente de Price

### Alternativas Não Testadas
1. **Playwright/Selenium**: Mais lento, mais complexo (não necessário por enquanto)
2. **API Key**: Carrefour pode ter programa de parceiros (investigar se necessário)
3. **GraphQL**: Verificar se Carrefour usa GraphQL API (não testado)

### Performance Otimizações Futuras
- [ ] Async HTTP com `asyncio` + `aiohttp` (já usa requests síncrono)
- [ ] Paralelização por região (atualmente `max_workers: 1`)
- [ ] Cache de sitemaps (evitar re-download)
- [ ] Retry logic para 404 temporários

---

## ✅ Checklist de Continuação

**Para retomar o trabalho**:

1. [ ] Decidir: Rodar scrape completo (~9h) ou continuar com teste (100 produtos)?
2. [ ] Criar DBT source para Carrefour
3. [ ] Criar staging model `stg_carrefour__products.sql`
4. [ ] Processar pipeline: `dbt run --select stg_carrefour__products+`
5. [ ] Adicionar Carrefour ao trusted layer (joins com outras stores)
6. [ ] Adicionar Carrefour aos marts (price comparison, promotions)
7. [ ] Atualizar dashboard com filtro de Carrefour
8. [ ] Documentar limitação de "list_price = price" (sem promoções por enquanto)

**Arquivos para consultar**:
- `src/ingest/scrapers/carrefour_html.py` - Scraper implementado
- `config/stores.yaml` - Configuração Carrefour
- `src/transform/dbt_project/models/staging/stg_bistek__products.sql` - Exemplo para Carrefour
- `docs/architecture/DATA_LAYERS.md` - Arquitetura do pipeline

---

## 🚀 Quick Start (Próxima Sessão)

```bash
# 1. Verificar status
git status
git log --oneline -5

# 2. Scrape completo (opcional - rodar overnight)
nohup python cli.py scrape carrefour --all > carrefour_scrape.log 2>&1 &

# 3. Criar DBT source
# Editar: src/transform/dbt_project/models/staging/sources.yml

# 4. Criar staging model
# Copiar: stg_bistek__products.sql -> stg_carrefour__products.sql

# 5. Testar pipeline
cd src/transform/dbt_project
dbt run --select stg_carrefour__products
dbt test --select stg_carrefour__products
```

---

**Última atualização**: 2026-02-06 11:30
**Commit atual**: `496dfd6`
**Status**: ✅ Pronto para DBT integration
