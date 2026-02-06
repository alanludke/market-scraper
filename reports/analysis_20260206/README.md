# Market Scraper - Relatório de Análise
**Data:** 06 de Fevereiro de 2026
**Período de Coleta:** 06/02/2026 01:26 - 01:32 (6.5 minutos)
**Versão:** 1.0

---

## 📊 Executive Summary

Este relatório apresenta a análise exploratória dos dados coletados de 3 redes de supermercados em Santa Catarina (Bistek, Fort e Giassi), totalizando **29,365 produtos únicos** distribuídos em **37 regiões**.

### Principais Métricas

| Métrica | Valor |
|---------|-------|
| **Produtos Únicos** | 29,365 |
| **Total de Registros** | 279,202 |
| **Regiões Cobertas** | 37 |
| **Lojas Cobertas** | 3 |
| **Marcas Diferentes** | 2,912 |
| **Dados Coletados** | 241 MB (Parquet comprimido) |
| **Tempo de Coleta** | 6.5 minutos |
| **Taxa de Coleta** | ~4,545 produtos/minuto |

---

## 🏪 Análise por Loja

### 1. Catálogo de Produtos

| Loja | Produtos Únicos | Regiões | Total Registros |
|------|----------------|---------|-----------------|
| **Bistek** | 9,954 | 13 | 84,752 |
| **Fort** | 9,847 | 7 | 65,399 |
| **Giassi** | 9,779 | 17 | 129,051 |

**Insights:**
- Bistek possui o maior catálogo único (9,954 produtos)
- Giassi tem a maior cobertura regional (17 regiões)
- Fort opera em 7 regiões com catálogo similar ao Bistek

### 2. Preços Médios

| Loja | Preço Médio | Preço Mínimo | Preço Máximo | Mediana |
|------|-------------|--------------|--------------|---------|
| **Bistek** | R$ 18.07 | R$ 0.79 | R$ 869.90 | R$ 11.97 |
| **Giassi** | R$ 20.33 | R$ 0.72 | R$ 1,289.00 | R$ 13.90 |
| **Fort** | R$ 29.57 | R$ 0.29 | R$ 1,788.49 | R$ 15.89 |

**Insights:**
- ✅ **Bistek** tem os **preços médios mais baixos** (R$ 18.07)
- ⚠️ **Fort** tem preços médios 63% mais altos que Bistek
- Mediana de preços: Bistek (R$ 11.97) < Giassi (R$ 13.90) < Fort (R$ 15.89)

### 3. Disponibilidade de Produtos

| Loja | Disponíveis | Indisponíveis | % Disponibilidade |
|------|-------------|---------------|-------------------|
| **Giassi** | 9,779 | 26 | 100.0% |
| **Bistek** | 9,952 | 4 | 100.0% |
| **Fort** | 8,625 | 5,100 | 87.6% |

**Insights:**
- ✅ Giassi e Bistek têm disponibilidade quase perfeita (100%)
- ⚠️ Fort tem 12.4% de produtos indisponíveis (5,100 produtos)

---

## 💰 Análise de Preços

### Distribuição de Preços

| Faixa de Preço | Produtos | Percentual |
|----------------|----------|------------|
| R$ 0-5 | 46,414 | 16.6% |
| R$ 5-10 | 63,224 | 22.6% |
| R$ 10-20 | 79,124 | 28.3% |
| R$ 20-50 | 69,191 | 24.8% |
| R$ 50-100 | 15,555 | 5.6% |
| R$ 100+ | 5,694 | 2.0% |

**Insights:**
- **67.5%** dos produtos custam entre R$ 5-50 (faixa mais comum)
- **28.3%** estão na faixa R$ 10-20 (maior concentração)
- Apenas **2%** custam acima de R$ 100

### Produtos Extremos

**5 Mais Baratos:**
1. Limão Tahiti - Fort - **R$ 0.29**
2. (Vários produtos na faixa R$ 0.29 - R$ 1.00)

**5 Mais Caros:**
1. Whisky Johnnie Walker Blue Label 21 Anos 750ml - Fort - **R$ 1,788.49**
2. Champagne Dom Pérignon Vintage Blanc 750ml - Fort - **R$ 1,699.00**
3. (Produtos premium na faixa R$ 500 - R$ 1,700)

---

## 🏷️ Análise de Marcas

### Top 5 Marcas (por volume de produtos)

| Marca | Produtos | Lojas |
|-------|----------|-------|
| **Bistek** | 703 | 1 |
| **Dove** | 346 | 3 |
| **Nivea** | 293 | 3 |
| **Sadia** | 267 | 3 |
| **Seara** | 260 | 3 |

**Insights:**
- Bistek tem **marca própria** com 703 produtos (7% do catálogo)
- Dove, Nivea, Sadia e Seara estão presentes nas **3 redes**
- Total de **2,912 marcas** diferentes no mercado

---

## 🌍 Análise Regional

### Top 10 Regiões (por volume de produtos)

| Região | Loja | Produtos |
|--------|------|----------|
| balneario_camboriu | Fort | 9,847 |
| saojose_belavista | Fort | 9,543 |
| palhoca_passavinte | Fort | 9,543 |
| itajai_saojoao | Fort | 9,440 |
| blumenau_itoupava | Fort | 9,344 |
| florianopolis_costeira | Fort | 9,317 |
| palhoca_pagani | Giassi | 8,859 |
| blumenau_victor_konder | Giassi | 8,795 |
| jaragua_centro | Giassi | 8,767 |
| sao_jose_areias | Giassi | 8,702 |

**Insights:**
- Fort tem regiões com **maior catálogo** (próximo ao catálogo completo)
- Giassi tem **maior cobertura** (17 regiões vs 13 Bistek vs 7 Fort)
- Balneário Camboriú (Fort) tem o maior catálogo regional (9,847 produtos)

---

## ⚡ Performance da Coleta

### Métricas de Performance

| Métrica | Valor |
|---------|-------|
| **Início** | 06/02/2026 01:26:18 |
| **Fim** | 06/02/2026 01:32:54 |
| **Duração Total** | 6 min 36 seg |
| **Produtos/minuto** | ~4,545 |
| **Dados Coletados** | 241 MB (Parquet) |
| **Taxa de Compressão** | ~80-90% vs JSONL |

**Insights:**
- ✅ Scrape **extremamente rápido** (6.5 min para 29K produtos)
- ✅ Parquet oferece **alta compressão** (241 MB vs ~2GB em JSON)
- ✅ **Execução paralela** funcionou perfeitamente (3 lojas simultâneas)

### Tempo por Loja

| Loja | Duração | Status |
|------|---------|--------|
| **Bistek** | 3 min 6 seg | ✅ SUCCESS |
| **Fort** | 5 min 26 seg | ✅ SUCCESS |
| **Giassi** | 6 min 38 seg | ✅ SUCCESS |

---

## 📈 Principais Descobertas

### 🎯 Pricing Insights

1. **Bistek é o mais barato** - Preço médio R$ 18.07 (63% mais barato que Fort)
2. **Fort é premium** - Produtos mais caros (Whisky R$ 1,788.49, Champagne R$ 1,699)
3. **Maioria dos produtos** está na faixa R$ 10-20 (28.3%)

### 🏪 Catálogo Insights

1. **Equilíbrio de catálogo** - As 3 lojas têm ~10K produtos cada
2. **Bistek tem marca própria** forte (703 produtos)
3. **2,912 marcas** competindo no mercado SC

### 🌍 Regional Insights

1. **Giassi domina em cobertura** - 17 regiões (46% do total)
2. **Fort tem catálogo mais completo** por região
3. **37 regiões** cobertas em Santa Catarina

### 📦 Disponibilidade

1. **Giassi e Bistek** têm disponibilidade perfeita (100%)
2. **Fort** precisa melhorar (87.6% disponibilidade)

---

## 📁 Arquivos Gerados

Este relatório inclui os seguintes arquivos CSV para análises adicionais:

1. **01_products_by_store.csv** - Overview de produtos por loja
2. **02_price_statistics.csv** - Estatísticas de preços
3. **03_availability.csv** - Disponibilidade de produtos
4. **04_top_brands.csv** - Top 20 marcas
5. **05_cheapest_products.csv** - 50 produtos mais baratos
6. **06_most_expensive_products.csv** - 50 produtos mais caros
7. **07_price_distribution.csv** - Distribuição por faixa de preço
8. **08_regions_statistics.csv** - Estatísticas por região

---

## 🔄 Próximos Passos Sugeridos

### Transformação DBT (Bronze → Silver → Gold)

1. **Silver Layer** - Deduplicação e limpeza
   - Criar `tru_product` com produtos únicos
   - Normalizar campos (preços, nomes, brands)
   - Adicionar flags de qualidade

2. **Gold Layer - Marts**
   - **Pricing Mart** - Comparação de preços entre lojas
   - **Catalog Mart** - Análise de sortimento
   - **Availability Mart** - Tracking de disponibilidade

### Análises Avançadas

1. **Comparação de preços** - Mesmo produto em lojas diferentes
2. **Análise de concorrência** - Quem tem produtos mais exclusivos?
3. **Time series** - Evolução de preços ao longo do tempo (com scrapes diários)
4. **Market basket** - Produtos frequentemente vendidos juntos

### Automação

1. **Scheduled scrapes** - GitHub Actions ou cron diário
2. **Alertas de preço** - Notificações quando produtos ficam mais baratos
3. **Dashboard Streamlit** - Visualização interativa dos dados

---

## 📞 Contato

**Projeto:** Market Scraper - Data Platform
**Autor:** Alan Ludke
**GitHub:** [alanludke/market-scraper](https://github.com/alanludke/market-scraper)
**Data do Relatório:** 06/02/2026

---

*Relatório gerado automaticamente pelo Market Scraper Analytics Pipeline*
