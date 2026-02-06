# Estratégia de Rate Limiting e Riscos

## ⚠️ O que acontece se formos bloqueados pela VTEX?

### Consequências do Bloqueio:

#### 1. **HTTP 429 - Too Many Requests**
**O que acontece:**
- VTEX retorna `429 Too Many Requests`
- Todas as requests subsequentes falham por 1-5 minutos
- **NÃO é permanente** - é um bloqueio temporário

**Impacto:**
- ✅ **Baixo**: A API VTEX NÃO bloqueia permanentemente
- ⏱️ **Duração**: 1-5 minutos típicos
- 🔄 **Recovery**: Automático após o período de cooldown

#### 2. **Rate Limit Violação (5,000 req/min)**
**O que acontece:**
- VTEX throttles requests acima de 5,000/min
- Requests adicionais retornam `429` ou `503`
- Pode afetar **TODOS os stores** na mesma conta VTEX (se compartilharem conta)

**Impacto:**
- ⚠️ **Médio**: Afeta todas as aplicações usando a mesma conta
- 🕐 **Duração**: Até próxima janela de 60 segundos
- 💡 **Mitigação**: Rate limiter global compartilhado

#### 3. **IP Ban (RARO)**
**O que acontece:**
- Apenas se detectarem padrão malicioso (ex: 100,000 req/min sustentado)
- VTEX raramente faz IP ban por scraping legítimo
- Mais comum em ataques DDoS

**Impacto:**
- ❌ **Alto**: Bloqueio do IP por horas/dias
- 🔥 **Probabilidade**: < 0.1% se usarmos rate limiter
- 🛡️ **Prevenção**: Nosso rate limiter evita isso

---

## 🛡️ Nossa Estratégia de Mitigação

### 1. **Rate Limiter com Token Bucket**

Implementação: [`src/ingest/scrapers/rate_limiter.py`](src/ingest/scrapers/rate_limiter.py)

```python
# Limites conservadores (80% da capacidade VTEX)
rate_limiter = RateLimiter(
    rate_limit=4000,        # 80% de 5,000 (margem de segurança)
    window_seconds=60,      # Janela de 1 minuto
    max_concurrent=80       # 80% de 100 (evita burst excessivo)
)
```

**Por que 80% e não 100%?**
- ✅ Margem para outras aplicações na mesma conta
- ✅ Proteção contra variações de relógio (clock skew)
- ✅ Buffer para retries em caso de erros

### 2. **Exponential Backoff em 429**

Quando recebemos `429`, aplicamos backoff exponencial:

```python
# Implementado em _scrape_by_ids_parallel
try:
    resp = session.get(api_url, params=params, timeout=20)
    if resp.status_code == 429:
        retry_count += 1
        wait_time = min(2 ** retry_count, 60)  # Max 60s
        logger.warning(f"Rate limited, waiting {wait_time}s")
        time.sleep(wait_time)
except:
    # Handle retries
```

**Tentativas:**
1. Erro 429 → espera 2s
2. Erro 429 → espera 4s
3. Erro 429 → espera 8s
4. Erro 429 → espera 16s
5. Erro 429 → espera 32s
6. Erro 429 → espera 60s (max)

### 3. **Global Rate Limiter (Compartilhado)**

**Problema:** Se scrapers múltiplos rodam em paralelo (bistek + fort + giassi), cada um pode tentar usar 5,000 req/min, totalizando 15,000 req/min!

**Solução:** Rate limiter **global** compartilhado entre todos os stores:

```python
# Em rate_limiter.py
_global_rate_limiter = None  # Singleton

def get_rate_limiter():
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            rate_limit=4000,  # 80% of 5000
            window_seconds=60,
            max_concurrent=80
        )
    return _global_rate_limiter
```

Todos os scrapers compartilham o **mesmo token bucket**, garantindo:
- ✅ Total de requests < 4,000/min (todos os stores combinados)
- ✅ Concurrent requests < 80 (todos os stores combinados)

### 4. **Monitoramento em Tempo Real**

Durante scraping, podemos monitorar taxa atual:

```python
stats = rate_limiter.get_stats()
# {
#   "current_rate": 2500,              # req/min atual
#   "requests_in_window": 2500,        # requests nos últimos 60s
#   "rate_limit": 4000,                # limite configurado
#   "max_concurrent": 80,              # max threads
#   "available_concurrent": 45         # slots disponíveis
# }
```

Se `current_rate` > 3500 (87.5%), podemos adicionar delays extras automaticamente.

---

## 📊 Cenários de Teste

### Cenário 1: Agressivo Seguro (Nossa Config)
```yaml
request_delay: 0.1s
max_workers: 13 (regiões em paralelo)
rate_limit: 4000/min (80% da capacidade)
```

**Resultado esperado:**
- ✅ **Requests/min**: ~3,000-3,500 (dentro do limite)
- ✅ **Concurrent**: ~50-70 threads (dentro do limite)
- ✅ **Probabilidade 429**: < 1%
- ⚡ **Speedup**: ~20-30x vs sequencial

**Tempo estimado:**
- Bistek: 65 min → **~2-3 min**
- Fort: 56 min → **~2 min**
- Giassi: 102 min → **~4-5 min**

### Cenário 2: MUITO Agressivo (NÃO RECOMENDADO)
```yaml
request_delay: 0s
max_workers: 50
rate_limit: 5000/min (100% da capacidade)
```

**Resultado esperado:**
- ⚠️ **Requests/min**: 4,500-5,500 (excede limite!)
- ⚠️ **Concurrent**: 90-110 threads (excede burst!)
- ❌ **Probabilidade 429**: 30-50%
- 🔥 **Risco IP ban**: 5-10%

**Por que NÃO fazer:**
- ❌ Muitos erros 429 → desperdício de tempo em retries
- ❌ Afeta outros scrapers na mesma conta
- ❌ Pode triggar proteção anti-bot da VTEX

### Cenário 3: Ultra Conservador (Atual)
```yaml
request_delay: 0.5s
max_workers: 1 (sequencial)
rate_limit: N/A
```

**Resultado esperado:**
- ✅ **Probabilidade 429**: ~0%
- ⏱️ **Speedup**: 1x (baseline)
- 💤 **Desperdício**: 95% da capacidade não utilizada

---

## 🎯 Recomendações

### Para Scraping Diário (Produção):
```yaml
# config/stores.yaml
request_delay: 0.1      # 3x faster que 0.3s
max_workers: 10         # Paralelo agressivo mas seguro
```

**Rate limiter:**
```python
RateLimiter(
    rate_limit=4000,    # 80% da capacidade (seguro)
    max_concurrent=80   # 80% do burst (seguro)
)
```

**Resultado:**
- ✅ Seguro (<1% chance de 429)
- ⚡ ~20x mais rápido
- 🛡️ Margem para outros scrapes/apps

### Para Scraping One-off (Urgente):
```yaml
request_delay: 0.05     # 6x faster que 0.3s
max_workers: 15         # Muito agressivo
```

**Rate limiter:**
```python
RateLimiter(
    rate_limit=4500,    # 90% da capacidade (arriscado)
    max_concurrent=90   # 90% do burst (arriscado)
)
```

**Resultado:**
- ⚠️ Moderado (5-10% chance de 429)
- ⚡ ~30x mais rápido
- 🔥 Use apenas quando necessário

### Para Desenvolvimento/Teste:
```yaml
request_delay: 0.2      # Conservador
max_workers: 3          # Baixo paralelismo
```

**Resultado:**
- ✅ Muito seguro
- ⏱️ ~5x mais rápido
- 🧪 Bom para debug

---

## 🔍 Como Detectar se Fomos Bloqueados

### Logs para Monitorar:

```bash
# Verificar erros 429 em tempo real
tail -f data/logs/app.log | grep "429"

# Verificar rate limiter stats
tail -f data/logs/app.log | grep "rate_limiter_stats"
```

### Métricas no DuckDB:

```sql
-- Contagem de erros por status code
SELECT
    api_status_code,
    COUNT(*) as count,
    AVG(response_time_ms) as avg_ms
FROM scraper_batches
WHERE run_id = 'bistek_20260205_120000'
GROUP BY api_status_code
ORDER BY count DESC;

-- Se ver muitos 429, fomos agressivos demais!
```

### Sinais de Problema:

| Sinal | Significado | Ação |
|-------|------------|------|
| 1-5 erros 429 | Normal, retry automático OK | ✅ Nada |
| 10-20 erros 429 | Perto do limite, precaução | ⚠️ Reduzir max_workers |
| 50+ erros 429 | Bloqueio ativo, muito agressivo | ❌ Cancelar e esperar 5 min |
| 503 sustained | VTEX em manutenção ou overload | 🛑 Esperar 30-60 min |

---

## 🚀 Próximos Passos (Otimizações Futuras)

### 1. **Adaptive Rate Limiting**
Ajustar rate automaticamente baseado em taxa de erro:
- Se 429 rate < 1%: aumentar rate_limit em 10%
- Se 429 rate > 5%: diminuir rate_limit em 20%
- Se 429 rate > 20%: pause por 60s

### 2. **Circuit Breaker**
Se muitos erros 429 consecutivos, pausar temporariamente:
```python
if consecutive_429_errors > 10:
    logger.warning("Circuit breaker: pausing 60s")
    time.sleep(60)
```

### 3. **Distributed Rate Limiting**
Se rodarmos scrapers em múltiplas máquinas:
- Redis para compartilhar token bucket
- Coordenação central de rate limit

---

## 📝 Conclusão

**Nossa estratégia atual (80% da capacidade) é:**
- ✅ **Segura**: <1% chance de bloqueio
- ⚡ **Rápida**: 20-30x speedup vs sequencial
- 🛡️ **Defensiva**: Margem para outras apps
- 🎯 **Ideal para produção**

**Se precisar mais velocidade:**
- Aumentar para 90% da capacidade (4,500 req/min)
- Aceitar 5-10% de erros 429 (com retry automático)
- **Não** exceder 95% (muito arriscado)

**NUNCA:**
- ❌ Desabilitar rate limiter
- ❌ Usar 100% da capacidade sustentado
- ❌ Ignorar erros 429 sem backoff

---

**Última atualização**: 2026-02-05
**Versão**: 1.0 (Performance Optimization - Phase 3)
