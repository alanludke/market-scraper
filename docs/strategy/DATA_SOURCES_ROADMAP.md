# Data Sources Roadmap
**Fontes de Dados Complementares para Market Scraper**

---

## 📋 Objetivo

Documentar fontes de dados estratégicas que podem ser integradas ao Market Scraper para agregar inteligência de negócio, enriquecer análises e gerar insights competitivos.

---

## 🎯 Fontes de Dados Prioritárias

### 1. **Base de EANs (GS1 Brasil / OpenFoodFacts)** ⭐ CRÍTICO

**O que é:**
- Código de barras internacional (EAN-13, GTIN-14) que identifica produtos univocamente
- Base de dados global de produtos com atributos padronizados

**Inteligência Agregada:**
- ✅ **Deduplicação cross-store**: Mesm produto pode ter nomes diferentes em lojas diferentes, mas EAN é único
- ✅ **Categorização padronizada**: Mapear produtos para taxonomias globais (GPC - Global Product Classification)
- ✅ **Atributos enriquecidos**: Peso líquido, país de origem, marca oficial, ingredientes
- ✅ **Análise nutricional**: Calorias, proteínas, gorduras (para alimentos)
- ✅ **Comparação precisa de preço**: Garantir que estamos comparando o **mesmo** produto (não variantes)
- ✅ **Detecção de substituições**: Identificar quando um produto foi descontinuado e substituído por outro

**Fontes Recomendadas:**
1. **OpenFoodFacts** (https://world.openfoodfacts.org)
   - API gratuita, open source
   - +2.5 milhões de produtos alimentícios
   - Dados colaborativos com validação comunitária
   - API: `https://world.openfoodfacts.org/api/v0/product/{ean}.json`

2. **GS1 Brasil** (https://gs1br.org)
   - Base oficial de EANs no Brasil
   - Requer pagamento/assinatura
   - Dados certificados e auditados

3. **Cosmos DB / Barcode Lookup** (https://www.barcodelookup.com)
   - API comercial (~$50/mês para 10k requests)
   - Cobertura global, incluindo não-alimentos

**Implementação Sugerida:**
```
bronze/
└── ean_master/
    ├── openfoodfacts_products.parquet
    └── gs1_brazil_registry.parquet

trusted/
└── tru_ean_master/
    ├── ean_code (PK)
    ├── product_name_canonical
    ├── brand_canonical
    ├── category_gpc
    ├── weight_net
    ├── country_of_origin
    └── nutritional_info (JSON)

gold/
└── dim_ean/
    ├── ean_key (surrogate)
    ├── ean_code (natural key)
    ├── product_name
    ├── brand
    ├── category_l1, category_l2, category_l3
    ├── is_food, is_beverage, is_organic
    └── nutritional_score (Nutri-Score A-E)
```

**KPIs Desbloqueados:**
- Price-per-gram comparison ($/kg normalization)
- Cross-store brand share analysis
- Nutritional value vs price correlation
- Organic premium pricing analysis

---

### 2. **Dados de Concorrentes (Web Scraping)** ⭐ ALTO

**O que é:**
- Preços de supermercados não-VTEX (Walmart, Carrefour, Extra, Pão de Açúcar)
- Dados de marketplaces (Mercado Livre, Amazon Fresh)

**Inteligência Agregada:**
- ✅ **Competitive benchmarking**: Comparar preços com concorrentes diretos
- ✅ **Price elasticity**: Entender como mudanças de preço afetam market share
- ✅ **Promotional strategy**: Analisar campanhas promocionais de concorrentes
- ✅ **Market positioning**: Identificar se lojas VTEX são premium, mid-market ou discount
- ✅ **Assortment gaps**: Produtos que concorrentes têm mas VTEX não

**Fontes Recomendadas:**
1. **Walmart Brasil** (walmart.com.br)
   - API pública limitada
   - Web scraping com Playwright/Selenium
   - ~50k SKUs no Brasil

2. **Carrefour** (carrefour.com.br)
   - VTEX platform (similar ao nosso scraper atual)
   - Reuse existing scraper architecture

3. **Mercado Livre** (mercadolivre.com.br)
   - API oficial (ML API v2)
   - +100M SKUs, incluindo supermercado
   - Rate limit: 5k requests/hour

4. **Cesta Básica DIEESE** (dieese.org.br)
   - Dataset público de preços de cesta básica
   - Histórico desde 1994
   - Benchmark oficial de inflação alimentar

**Implementação Sugerida:**
```
bronze/
├── competitor_walmart/
├── competitor_carrefour/
├── competitor_mercadolivre/
└── benchmark_dieese/

trusted/
└── tru_competitor_prices/
    ├── source_system (walmart, carrefour, ml)
    ├── product_id_external
    ├── ean_code (for matching)
    ├── product_name
    ├── price
    ├── scraped_date

gold/
└── fct_competitive_pricing/
    ├── product_key (FK to dim_ean)
    ├── our_price (VTEX stores average)
    ├── walmart_price
    ├── carrefour_price
    ├── ml_price
    ├── price_gap_vs_market
    ├── is_cheapest_in_market
    └── competitive_position_rank
```

**KPIs Desbloqueados:**
- Price gap analysis (quanto mais caro/barato que concorrência)
- Market share estimation (via assortment overlap)
- Promotional war detection (sincronização de promoções)

---

### 3. **Reviews e Ratings (NLP Sentiment Analysis)** ⭐ MÉDIO

**O que é:**
- Avaliações de clientes sobre produtos (ReclameAqui, Google Reviews, VTEX Reviews)
- Sentimento de marca e qualidade percebida

**Inteligência Agregada:**
- ✅ **Quality vs Price correlation**: Produtos baratos são mal avaliados?
- ✅ **Brand perception**: Marcas premium têm reviews melhores?
- ✅ **Complaint patterns**: Produtos com recalls ou defeitos recorrentes
- ✅ **Recommendation systems**: Produtos similares com melhor avaliação
- ✅ **Churn prediction**: Reviews ruins → clientes vão para concorrência?

**Fontes Recomendadas:**
1. **VTEX Reviews API** (nativa da plataforma)
   - Endpoint: `/api/reviews-and-ratings/pvt/reviews`
   - Dados estruturados (rating 1-5, text, verified purchase)

2. **ReclameAqui API** (www.reclameaqui.com.br)
   - Web scraping necessário
   - Reclamações por marca/produto

3. **Google Shopping Reviews**
   - Google Merchant Center API
   - Requer autenticação OAuth

**Implementação Sugerida:**
```
bronze/
└── reviews/
    ├── vtex_reviews.parquet
    └── reclameaqui_complaints.parquet

trusted/
└── tru_product_reviews/
    ├── product_id
    ├── ean_code
    ├── review_text
    ├── rating (1-5)
    ├── sentiment_score (-1 to 1, via NLP)
    ├── is_verified_purchase
    └── reviewed_date

gold/
└── fct_product_quality/
    ├── product_key
    ├── avg_rating
    ├── review_count
    ├── sentiment_avg
    ├── quality_tier (A-D based on rating + sentiment)
    └── price_quality_ratio
```

**KPIs Desbloqueados:**
- Quality-adjusted price comparison
- Brand reputation score
- Products at risk (low rating + high visibility)

---

### 4. **Dados Macroeconômicos (IBGE / Banco Central)** ⭐ MÉDIO

**O que é:**
- Índices de inflação (IPCA, INPC)
- Taxa de juros (SELIC)
- Salário mínimo, desemprego, PIB regional

**Inteligência Agregada:**
- ✅ **Real vs Nominal price analysis**: Ajustar preços pela inflação
- ✅ **Seasonal patterns**: Preços sobem mais em datas festivas?
- ✅ **Economic elasticity**: Preços reagem a mudanças na SELIC?
- ✅ **Regional purchasing power**: Regiões com maior poder de compra pagam mais?

**Fontes Recomendadas:**
1. **IBGE API** (servicodados.ibge.gov.br/api/v3)
   - IPCA, INPC, PIB, população
   - API pública, sem rate limits

2. **Banco Central API** (https://api.bcb.gov.br)
   - SELIC, câmbio, reservas
   - Dados históricos desde 1980

3. **DIEESE** (dieese.org.br)
   - Custo da cesta básica por região
   - Salário mínimo necessário

**Implementação Sugerida:**
```
bronze/
└── macroeconomic/
    ├── ibge_ipca.parquet
    ├── bcb_selic.parquet
    └── dieese_basket.parquet

gold/
└── dim_economic_indicators/
    ├── date_key (FK to dim_date)
    ├── ipca_index
    ├── selic_rate
    ├── unemployment_rate
    └── basket_cost_florianopolis
```

**KPIs Desbloqueados:**
- Inflation-adjusted price trends
- Price sensitivity to interest rates

---

### 5. **Dados de Tráfego Web (Google Analytics / SEMrush)** ⭐ BAIXO

**O que é:**
- Visitas ao site, conversão, cliques em produtos
- Keywords de busca orgânica

**Inteligência Agregada:**
- ✅ **Product visibility**: Produtos mais visualizados vs mais vendidos
- ✅ **Conversion funnel**: % de visitantes que compram
- ✅ **SEO optimization**: Keywords que trazem mais tráfego
- ✅ **Abandoned cart analysis**: Produtos no carrinho mas não comprados

**Fontes Recomendadas:**
1. **Google Analytics 4 API**
   - Requer acesso ao GA do cliente
   - Dados de sessão, conversão, eventos

2. **VTEX Checkout API**
   - Dados transacionais (orders, items, payments)
   - Endpoint: `/api/checkout/pvt/orders`

**Implementação Sugerida:**
```
bronze/
└── web_analytics/
    ├── ga4_sessions.parquet
    └── vtex_orders.parquet

gold/
└── fct_product_performance/
    ├── product_key
    ├── pageviews
    ├── add_to_cart_rate
    ├── conversion_rate
    ├── revenue
    └── profit_margin (se custo disponível)
```

---

### 6. **Dados de Clima (OpenWeatherMap / INMET)** ⭐ BAIXO

**O que é:**
- Temperatura, precipitação, umidade por região

**Inteligência Agregada:**
- ✅ **Weather-driven demand**: Sorvetes vendem mais no calor?
- ✅ **Seasonal pricing**: Preços sobem em dias de chuva (delivery)?

**Fontes Recomendadas:**
1. **OpenWeatherMap API** (openweathermap.org)
   - Gratuito até 1k requests/dia
   - Dados históricos + forecast

2. **INMET API** (api.inmet.gov.br)
   - Dados oficiais do governo brasileiro
   - Histórico desde 1960

---

## 🔄 Priorização de Implementação

### Fase 1 (Próximos 3 meses) - **Fundamentais**
1. ✅ **Base de EANs (OpenFoodFacts)** - Deduplicação e categorização
2. ✅ **Concorrentes (Carrefour + Walmart)** - Competitive benchmarking

### Fase 2 (3-6 meses) - **Enriquecimento**
3. ✅ **Reviews (VTEX + ReclameAqui)** - Quality analysis
4. ✅ **Macroeconômicos (IBGE + BCB)** - Inflation adjustment

### Fase 3 (6-12 meses) - **Avançado**
5. ✅ **Web Analytics (GA4)** - Conversion funnel
6. ✅ **Clima (INMET)** - Weather correlation

---

## 📊 Impacto Esperado por Fonte

| Fonte de Dados | Complexidade | ROI Estimado | Prazo Implementação |
|----------------|--------------|--------------|---------------------|
| **EANs** | Baixa | ALTO | 2-3 semanas |
| **Concorrentes** | Média | ALTO | 4-6 semanas |
| **Reviews** | Média | MÉDIO | 3-4 semanas |
| **Macroeconômicos** | Baixa | MÉDIO | 1-2 semanas |
| **Web Analytics** | Alta | ALTO | 6-8 semanas |
| **Clima** | Baixa | BAIXO | 1-2 semanas |

---

## 🎯 KPIs Desbloqueados por Combinação de Fontes

### Análise de Value-for-Money
**Fontes:** EANs + Reviews + Preços
- KPI: `(Avg Rating × Quality Score) / Price per Gram`
- Identificar produtos com melhor custo-benefício

### Competitive Intelligence Dashboard
**Fontes:** Concorrentes + Preços + Promoções
- KPI: `Price Gap %`, `Promotional Intensity`, `Market Share Proxy`
- Alertas quando concorrentes lançam promoções agressivas

### Economic-Adjusted Pricing
**Fontes:** Macroeconômicos + Preços
- KPI: `Real Price (inflation-adjusted)`, `Affordability Index`
- Analisar poder de compra real vs nominal

### Product Lifecycle Analysis
**Fontes:** EANs + Reviews + Web Analytics
- KPI: `Introduction Stage`, `Growth Stage`, `Maturity`, `Decline`
- Detectar produtos em fim de vida (baixo tráfego + reviews antigas)

---

## 🚀 Próximos Passos

1. **Validar acesso a APIs**:
   - [ ] Testar OpenFoodFacts API com EANs do bronze
   - [ ] Investigar acesso a VTEX Reviews API (requer auth?)
   - [ ] Configurar scraper Carrefour (reusar VTEXScraper)

2. **Criar schemas Pydantic**:
   - [ ] `EANProduct` (OpenFoodFacts response)
   - [ ] `CompetitorProduct` (generic schema)
   - [ ] `ProductReview` (VTEX + ReclameAqui)

3. **Modelagem DBT**:
   - [ ] `dim_ean` (EAN master dimension)
   - [ ] `fct_competitive_pricing` (cross-store price comparison)
   - [ ] `fct_product_quality` (reviews + ratings)

4. **Documentar integrações**:
   - [ ] API endpoints, rate limits, authentication
   - [ ] Exemplo de requests/responses
   - [ ] Error handling strategies

---

**Última atualização**: 2026-02-06
**Responsável**: Data Engineering Team
**Revisão**: Trimestral
