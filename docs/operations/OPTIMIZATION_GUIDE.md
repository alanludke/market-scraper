# Guia de Otimizações - Scraping Performance

## 📊 Resumo das Otimizações Implementadas

Data: 2026-02-07
Versão: 1.0

### Mudanças Realizadas

#### 1️⃣ Scraping Incremental (Maior Impacto!)

**Arquivo modificado**: `src/orchestration/scraper_flow.py`

**O que mudou**:
- ✅ Adicionado parâmetro `use_incremental` (default: `True`)
- ✅ Adicionado parâmetro `incremental_days` (default: `7`)
- ✅ Flow automaticamente passa flag `--incremental` para CLI

**Como usar**:

```python
# Run diária (incremental - apenas últimos 7 dias)
daily_scraper_flow()

# Full scraping mensal (catálogo completo)
daily_scraper_flow(use_incremental=False)

# Incremental customizado (últimos 14 dias)
daily_scraper_flow(incremental_days=14)
```

**Ganho esperado**: **8-16x mais rápido** (8h → 30-60 min)

---

#### 2️⃣ Request Delay Otimizado

**Arquivo modificado**: `config/stores.yaml`

**Mudanças**:
- Angeloni: `request_delay: 0.3` → `0.1` (3x mais rápido)
- Carrefour: `request_delay: 0.3` → `0.1` (3x mais rápido)
- SuperKoch: `request_delay: 0.3` → `0.1` (3x mais rápido)

**Justificativa**:
- APIs VTEX (Bistek, Fort, Giassi) já usam 0.1s com sucesso
- Reduz tempo total sem causar rate limiting
- Compatível com boas práticas de scraping

**Ganho esperado**: **3x mais rápido** (8h → 2.7h para full scraping)

---

#### 3️⃣ Batch Size Aumentado

**Arquivo modificado**: `config/stores.yaml`

**Mudanças**:
- Angeloni: `batch_size: 20` → `50`
- Carrefour: `batch_size: 20` → `50`
- SuperKoch: `batch_size: 20` → `50`

**Benefícios**:
- Menos arquivos Parquet gerados (498 → ~200)
- Reduz overhead de I/O
- Facilita processamento downstream (DBT)

**Ganho esperado**: **10-15% mais rápido**

---

## 🎯 Resultados Esperados

### Performance Comparativa

| Métrica | ANTES | DEPOIS | Melhoria |
|---------|-------|--------|----------|
| **Full Scraping** | 8h | 2.7h | **3x mais rápido** |
| **Incremental (7d)** | N/A | 30-60 min | **8-16x vs full** |
| **Arquivos/batch** | 498 | ~200 | **60% menos arquivos** |
| **Overhead I/O** | Alto | Baixo | **10-15% redução** |

### Cenários de Uso

#### 📅 Runs Diárias (Recomendado: Incremental)

```bash
# Via Prefect
prefect deployment run daily-scraper/daily-scraper

# Ou via Python
python src/orchestration/scraper_flow.py
```

**Configuração**:
- Modo: Incremental (últimos 7 dias)
- Tempo estimado: **30-60 minutos**
- Produtos: ~500-1,000 (apenas novos/modificados)
- Economia: **~85% do tempo**

#### 🔄 Runs Mensais (Full Refresh)

```bash
# Via Prefect (passar parâmetro via JSON)
prefect deployment run daily-scraper/daily-scraper \
  --param use_incremental=false

# Ou via Python
python -c "from src.orchestration.scraper_flow import daily_scraper_flow; daily_scraper_flow(use_incremental=False)"
```

**Configuração**:
- Modo: Full catalog
- Tempo estimado: **2.7 horas**
- Produtos: ~10,000 (catálogo completo)
- Redução: **8h → 2.7h (3x mais rápido)**

---

## 🧪 Como Testar

### 1. Teste Rápido (Incremental com Limite)

```bash
# Teste com apenas 100 produtos (validar que --incremental funciona)
python scripts/cli.py scrape angeloni --incremental 7 --limit 100
```

**Validação esperada**:
- ✅ Log mostra "Incremental discovery" com data de corte
- ✅ Apenas produtos modificados nos últimos 7 dias são descobertos
- ✅ Tempo: ~5-10 minutos para 100 produtos

### 2. Teste Full (Uma Loja)

```bash
# Teste full scraping de uma loja com novas configs
python scripts/cli.py scrape angeloni --region florianopolis_centro
```

**Validação esperada**:
- ✅ `request_delay` de 0.1s está sendo respeitado
- ✅ Batches com ~50 produtos (não 20)
- ✅ Tempo reduzido ~3x comparado com runs anteriores

### 3. Teste Prefect Flow (Incremental)

```bash
# Rodar flow incremental localmente
python src/orchestration/scraper_flow.py
```

**Validação esperada**:
- ✅ Flag `--incremental 7` é passada para CLI
- ✅ Log mostra "INCREMENTAL (last 7 days)"
- ✅ Resumo final mostra "Time saved: ~85%"

---

## 📊 Monitoramento

### Métricas a Acompanhar

1. **Tempo de Execução**
   ```bash
   # Verificar duração das runs no Prefect Dashboard
   # http://127.0.0.1:4200
   ```

2. **Produtos Descobertos**
   ```bash
   # Comparar incremental vs full
   # Incremental deveria descobrir ~10-20% do catálogo
   ```

3. **Rate Limiting (HTTP 429)**
   ```bash
   # Monitorar logs para erros 429
   tail -f data/logs/app.log | grep -i "429\|rate limit"
   ```

4. **Tamanho dos Batches**
   ```bash
   # Verificar que batches têm ~50 produtos
   python -c "import duckdb; conn = duckdb.connect('data/analytics.duckdb'); print(conn.execute('SELECT COUNT(*) FROM read_parquet(\"data/bronze/supermarket=angeloni/**/batches/batch_00001.parquet\")').fetchone())"
   ```

---

## ⚠️ Possíveis Problemas e Soluções

### Problema 1: Rate Limiting (HTTP 429)

**Sintoma**: Logs mostram erros "429 Too Many Requests"

**Solução**:
```yaml
# Em config/stores.yaml, aumentar delay
request_delay: 0.15  # ou 0.2
```

### Problema 2: Incremental não encontra produtos

**Sintoma**: Scraping incremental descobre 0 produtos

**Causa**: Nenhum produto foi modificado nos últimos 7 dias

**Solução**:
```bash
# Aumentar janela temporal
python scripts/cli.py scrape angeloni --incremental 14
```

### Problema 3: Batches muito grandes (OOM)

**Sintoma**: Erro de memória ao processar batches

**Solução**:
```yaml
# Em config/stores.yaml, reduzir batch_size
batch_size: 30  # em vez de 50
```

---

## 📅 Roadmap Futuro (Fase 2 e 3)

### Fase 2: Paralelização (1-2 meses)
- [ ] Converter `requests` → `aiohttp` (async/await)
- [ ] Processar 5-10 produtos simultaneamente
- [ ] Ganho estimado: **3-5x mais rápido** (2.7h → ~45 min)

### Fase 3: Cache Avançado (2-3 meses)
- [ ] Hash-based deduplication
- [ ] Smart retry com cache local
- [ ] Ganho estimado: Incremental → **15-20 min**

---

## 📚 Referências

- [CLAUDE.md](CLAUDE.md) - Arquitetura geral
- [src/orchestration/scraper_flow.py](src/orchestration/scraper_flow.py) - Código do flow
- [config/stores.yaml](config/stores.yaml) - Configurações de delays e batches
- [src/ingest/scrapers/angeloni_html.py](src/ingest/scrapers/angeloni_html.py) - Implementação do scraping incremental

---

**Última atualização**: 2026-02-07
**Versão**: 1.0
**Autor**: Claude Code (Otimização Fase 1)
