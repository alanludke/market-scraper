# Hot Deal Validation - Validação de Promoções por Scraping

## 📋 Visão Geral

O **Hot Deal Validator** é uma ferramenta que valida se as promoções anunciadas ainda estão ativas, fazendo scraping das páginas de produtos.

**Por que isso é importante?**
- Promoções podem expirar antes do esperado
- Preços podem mudar ao longo do dia
- Garantir que os dados apresentados aos usuários estão corretos
- Identificar problemas com a coleta de dados (ex: scraper pegou preço errado)

---

## 🚀 Como Usar

### 1. CLI - Linha de Comando

```bash
# Instalar dependências
pip install aiohttp beautifulsoup4

# Validar todos os hot deals (desconto >= 30%)
python cli_validate_deals.py --all

# Validar apenas top 50 deals
python cli_validate_deals.py --limit 50

# Validar apenas uma loja específica
python cli_validate_deals.py --store bistek --limit 20

# Salvar resultados em CSV
python cli_validate_deals.py --all --output data/validation_results.csv

# Salvar resultados no banco de dados
python cli_validate_deals.py --all --save-to-db
```

### 2. Python Script

```python
from src.analytics.hot_deal_validator import validate_hot_deals_sync
import duckdb
import pandas as pd

# Carregar hot deals do banco
conn = duckdb.connect('data/analytics.duckdb', read_only=True)
hot_deals = conn.execute("""
    SELECT
        product_id,
        product_name,
        store_id as supermarket,
        promotional_price as promo_price,
        discount_percentage as discount_pct,
        product_url
    FROM dev_local.fct_active_promotions
    WHERE discount_percentage >= 30
    LIMIT 100
""").df()

# Validar
validated = validate_hot_deals_sync(hot_deals)

# Ver resultados
print(validated[['product_name', 'is_deal_valid', 'validation_status']])
```

### 3. Integração Automática (Diária)

Adicionar ao cron ou GitHub Actions para executar diariamente após o scrape:

```yaml
# .github/workflows/daily_validation.yml

name: Daily Hot Deal Validation

on:
  schedule:
    - cron: '30 3 * * *'  # 3:30 AM UTC (30min após o scrape)
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Validate hot deals
        run: python cli_validate_deals.py --all --save-to-db --output data/validation_results.csv
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: validation-results
          path: data/validation_results.csv
```

---

## 📊 Output - Colunas Adicionadas

O validador adiciona as seguintes colunas ao DataFrame:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `validation_status` | string | `active`, `expired`, `error`, `no_url` |
| `current_price_scraped` | float | Preço atual encontrado na página |
| `current_discount_scraped` | float | Desconto atual encontrado na página |
| `is_deal_valid` | bool | Se o deal ainda está válido (dentro da tolerância) |
| `validation_error` | string | Mensagem de erro (se houver) |
| `validated_at` | timestamp | Data/hora da validação |

---

## ⚙️ Como Funciona

### 1. Extração de Dados

O validador tenta 3 estratégias para extrair preços das páginas VTEX:

#### Estratégia 1: JSON-LD (Schema.org)
```html
<script type="application/ld+json">
{
  "@type": "Product",
  "offers": {
    "price": 19.99,
    "highPrice": 39.99
  }
}
</script>
```

#### Estratégia 2: window.__INITIAL_STATE__ (VTEX IO)
```javascript
window.__INITIAL_STATE__ = {
  product: {
    items: [{
      sellers: [{
        price: 19.99
      }]
    }]
  }
}
```

#### Estratégia 3: Fallback - Seletores CSS
```html
<span class="vtex-product-price-1-x-sellingPrice">R$ 19,99</span>
<span class="vtex-product-price-1-x-listPrice">R$ 39,99</span>
```

### 2. Validação com Tolerância

Ao comparar o preço/desconto esperado vs atual, usamos tolerâncias:
- **Preço**: ±5% (para evitar falsos positivos por centavos de diferença)
- **Desconto**: -10% (ok se desconto for até 10% menor que o anunciado)

**Exemplo:**
```python
# Deal anunciado: R$ 20,00 com 50% de desconto
expected_price = 20.00
expected_discount = 50.0

# Preço atual encontrado: R$ 20,90 com 48% de desconto
current_price = 20.90
current_discount = 48.0

# Validação:
is_price_valid = 20.90 <= 20.00 * 1.05  # 20.90 <= 21.00 ✅
is_discount_valid = 48.0 >= 50.0 * 0.9   # 48.0 >= 45.0 ✅

is_deal_valid = True  # Deal ainda válido!
```

### 3. Execução Paralela

Valida múltiplos deals em paralelo usando `asyncio`:
- **Max 10 requisições simultâneas** (ajustável)
- **Timeout de 15s** por requisição
- **Semáforo** para evitar sobrecarga do servidor

---

## 📈 Interpretando Resultados

### Status: `active`
✅ Deal válido! Preço e desconto confirmados.

### Status: `expired`
⏰ Deal expirou. Preço ou desconto não correspondem mais.

**Ação recomendada:**
- Verificar se o scraper está funcionando corretamente
- Atualizar a data de expiração da promoção no banco
- Marcar deal como inativo

### Status: `error`
❌ Erro ao validar (timeout, página fora do ar, etc.)

**Ação recomendada:**
- Tentar novamente mais tarde
- Verificar se a URL está correta
- Checar logs para detalhes do erro

### Status: `no_url`
🔗 Produto não tem URL no banco de dados.

**Ação recomendada:**
- Verificar se o scraper está salvando URLs
- Adicionar campo `product_url` ao schema

---

## 🔧 Troubleshooting

### Erro: "Não foi possível extrair dados do produto"

**Causa:** Página VTEX mudou estrutura HTML/JSON.

**Solução:**
1. Abrir a URL manualmente no navegador
2. Inspecionar o código-fonte
3. Identificar novos seletores CSS ou estrutura JSON
4. Atualizar `_extract_from_html()` em `hot_deal_validator.py`

### Erro: "Timeout"

**Causa:** Página demorou muito para carregar.

**Solução:**
- Aumentar timeout: `HotDealValidator(timeout=30)`
- Verificar conexão de internet
- Tentar novamente em horário de baixo tráfego

### Erro: "HTTP 403 Forbidden"

**Causa:** Site bloqueou o scraper (anti-bot).

**Solução:**
- Adicionar headers realistas (User-Agent, Accept, etc.)
- Adicionar delays entre requisições
- Usar rotação de proxies (se necessário)

---

## 📊 Métricas e Alertas

### Métricas Recomendadas

- **Taxa de validação**: % de deals válidos vs total
- **Taxa de erro**: % de erros vs total
- **Latência média**: Tempo médio por validação
- **Deals expirados**: Contagem de deals que expiraram

### Alertas Sugeridos

```python
# Exemplo de alertas
validated = validate_hot_deals_sync(hot_deals)

valid_rate = validated['is_deal_valid'].mean()
error_rate = (validated['validation_status'] == 'error').mean()

# Alerta 1: Taxa de validação baixa
if valid_rate < 0.80:  # Menos de 80% válidos
    send_alert(f"⚠️ Taxa de validação baixa: {valid_rate:.1%}")

# Alerta 2: Taxa de erro alta
if error_rate > 0.20:  # Mais de 20% de erros
    send_alert(f"❌ Taxa de erro alta: {error_rate:.1%}")

# Alerta 3: Muitos deals expirados
expired_count = (validated['validation_status'] == 'expired').sum()
if expired_count > 50:
    send_alert(f"⏰ {expired_count} deals expirados - verificar scraper!")
```

---

## 🎯 Casos de Uso

### 1. Auditoria Diária
Executar diariamente após o scrape para garantir qualidade dos dados.

### 2. Investigação de Problemas
Quando usuários reportam preços incorretos, usar validação para confirmar.

### 3. Dashboard de Confiabilidade
Criar dashboard mostrando histórico de taxas de validação por loja.

### 4. Alertas em Tempo Real
Integrar com sistema de alertas para notificar quando muitos deals expirarem.

---

## 📚 Próximos Passos

- [ ] Adicionar suporte para lojas não-VTEX
- [ ] Implementar cache de validações (evitar validar o mesmo produto múltiplas vezes)
- [ ] Adicionar validação de disponibilidade em estoque
- [ ] Criar dashboard visual de validações no Streamlit
- [ ] Integrar com Great Expectations para data quality checks

---

**Última atualização:** 2026-02-06
**Autor:** Claude Sonnet 4.5
