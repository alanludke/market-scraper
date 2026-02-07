# Scraper Performance & Rate Limiting Documentation

**Last updated**: 2026-02-07
**Version**: 1.0

## Overview

Este documento detalha as configurações de performance, rate limiting, e estratégias de paralelização de todos os scrapers da plataforma. O objetivo é garantir que estamos utilizando **80-90% da capacidade máxima das APIs/sites** sem ser bloqueados ou causar problemas nos servidores.

---

## 1. VTEX Scrapers (API-based)

### 1.1 Rate Limiting Global (Compartilhado)

**Arquitetura**: Todos os scrapers VTEX (Bistek, Fort, Giassi) compartilham um **único rate limiter global** porque o limite da VTEX é **por conta**, não por loja.

**Implementação**: [`src/ingest/scrapers/rate_limiter.py`](../../src/ingest/scrapers/rate_limiter.py)

```python
class RateLimiter:
    """
    Token bucket rate limiter with burst support.

    Configuração padrão (VTEX API limits):
    - rate_limit: 5000 requests/minute
    - max_concurrent: 100 requests (burst)
    - window_seconds: 60s (sliding window)
    """
```

#### Limites da API VTEX (Oficial)
- **5,000 requests/minute** por conta
- **100 concurrent requests** (burst)
- Sliding window de 60 segundos

#### Nossa Configuração (80% do limite)
- **Rate limit**: 5,000 req/min (100% - usamos o máximo, pois o rate limiter controla com sliding window)
- **Max concurrent**: 100 (100% - controlado pelo semaphore thread-safe)
- **Estratégia**: Token bucket com sliding window (remove requisições antigas automaticamente)

**Verificação**:
```python
# Todos os scrapers VTEX usam o mesmo rate limiter global
rate_limiter = get_rate_limiter()  # Singleton compartilhado

# Durante scraping paralelo:
with self.rate_limiter.limit():
    resp = session.get(api_url, params=params, timeout=20)
```

**Status**: ✅ **Otimizado** - Usamos 100% da capacidade de forma controlada (rate limiter previne ultrapassar o limite)

---

### 1.2 Bistek (VTEX API)

**Plataforma**: VTEX
**Discovery**: Sitemap (fast path)
**Estratégia**: Global discovery → Parallel region scraping

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **50** | VTEX API aceita até 50 produtos por request (máximo) | ✅ **100%** |
| `request_delay` | **0.1s** | Delay mínimo entre requests (10 req/s por thread) | ✅ **Otimizado** |
| `max_workers` | **13** | Scraping paralelo de 13 regiões simultaneamente | ✅ **Paralelo** |
| Rate limit (global) | 5000 req/min | Compartilhado com Fort e Giassi | ✅ **Controlado** |
| Max concurrent | 100 | Semaphore global thread-safe | ✅ **Controlado** |

#### Throughput Estimado

**Scraping paralelo (13 workers)**:
- 13 regiões em paralelo (ThreadPoolExecutor)
- Cada worker faz ~10 req/s (delay 0.1s)
- Throughput teórico: **130 req/s** (7,800 req/min) → **limitado pelo rate limiter global a 5,000 req/min**
- Throughput real: **~83 req/s** (5,000 req/min ÷ 60s)

**Observação**: O rate limiter global garante que nunca ultrapassamos 5,000 req/min mesmo com paralelização agressiva.

**Status**: ✅ **Excelente** - Utiliza 100% da capacidade VTEX de forma controlada, com paralelização máxima por região.

---

### 1.3 Fort Atacadista (VTEX API)

**Plataforma**: VTEX
**Discovery**: Category tree (sitemap desatualizado)
**Estratégia**: Global discovery → Parallel region scraping

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **50** | VTEX API máximo | ✅ **100%** |
| `request_delay` | **0.1s** | Otimizado (era 0.3s, agora 3x mais rápido) | ✅ **Otimizado** |
| `max_workers` | **7** | Scraping paralelo de 7 regiões | ✅ **Paralelo** |
| Rate limit (global) | 5000 req/min | Compartilhado com Bistek e Giassi | ✅ **Controlado** |

#### Throughput Estimado

**Scraping paralelo (7 workers)**:
- 7 regiões em paralelo
- Cada worker: ~10 req/s (delay 0.1s)
- Throughput teórico: **70 req/s** → limitado pelo rate limiter global

**Status**: ✅ **Excelente** - Otimizado recentemente (3x mais rápido após reduzir delay de 0.3s → 0.1s)

---

### 1.4 Giassi (VTEX API)

**Plataforma**: VTEX
**Discovery**: Category tree (sitemap desatualizado)
**Estratégia**: Global discovery → Parallel region scraping

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **50** | VTEX API máximo | ✅ **100%** |
| `request_delay` | **0.1s** | Otimizado (era 0.2s, agora 2x mais rápido) | ✅ **Otimizado** |
| `max_workers` | **17** | Scraping paralelo de 17 regiões (máximo!) | ✅ **Paralelo** |
| Rate limit (global) | 5000 req/min | Compartilhado com Bistek e Fort | ✅ **Controlado** |

#### Throughput Estimado

**Scraping paralelo (17 workers)**:
- 17 regiões em paralelo (maior paralelização!)
- Cada worker: ~10 req/s (delay 0.1s)
- Throughput teórico: **170 req/s** → **limitado pelo rate limiter global a 83 req/s**

**Observação**: O Giassi tem o maior número de regiões (17), então o rate limiter global é especialmente importante para evitar ultrapassar o limite.

**Status**: ✅ **Excelente** - Máxima paralelização possível, controlada pelo rate limiter global.

---

### 1.5 Análise Consolidada (VTEX Scrapers)

**Rate Limiting Compartilhado**:
```
Total max_workers: 13 (Bistek) + 7 (Fort) + 17 (Giassi) = 37 workers teóricos

SE todos scraperem simultaneamente:
- Throughput teórico: 370 req/s (22,200 req/min)
- Limite VTEX: 5,000 req/min (83 req/s)
- Rate limiter: BLOQUEIA automaticamente e distribui capacidade

Resultado: Cada scraper recebe ~83 req/s ÷ 37 workers = 2.2 req/s por worker
```

**Status**: ✅ **Excelente** - O rate limiter global garante que NUNCA ultrapassamos os limites da VTEX, mesmo rodando múltiplos scrapers simultaneamente.

**Recomendação**: ✅ **Manter configuração atual**. O rate limiter thread-safe distribui automaticamente a capacidade disponível entre todos os workers ativos.

---

## 2. HTML Scrapers (Scraping Direto)

### 2.1 Estratégia Geral

**Diferenças em relação aos scrapers VTEX**:
1. **Sem rate limiting global** (cada site tem suas próprias políticas)
2. **Request delay mais conservador** (0.5s vs 0.1s) para evitar bloqueios
3. **Batch size menor** (20 vs 50) - HTML é mais lento que API
4. **Sem paralelização** (max_workers=1) - mais respeitoso com servidores

---

### 2.2 Carrefour (HTML Scraping)

**Plataforma**: VTEX (API bloqueada com 503)
**Discovery**: Sitemap
**Scraping**: JSON-LD extraction from HTML pages

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **20** | Menor que VTEX API (HTML é mais lento) | ✅ **Conservador** |
| `request_delay` | **0.5s** | 5x mais lento que VTEX API (2 req/s) | ✅ **Conservador** |
| `max_workers` | **1** | Sem paralelização (sequential scraping) | ✅ **Respeitoso** |
| Rate limit | N/A | Sem rate limiter (controlado por delay) | ⚠️ **Manual** |

#### Throughput Estimado

**Scraping sequencial**:
- 1 região por vez
- ~2 req/s (delay 0.5s)
- Throughput: **120 req/min** (2 req/s × 60s)

**Por que 0.5s de delay?**
- HTML scraping é mais "visível" que API (User-Agent, parsing, etc.)
- Evita bloqueios por rate limiting não documentado
- Mais respeitoso com o servidor (não sobrecarrega)

**Status**: ✅ **Conservador e seguro** - Configuração apropriada para HTML scraping sem rate limit explícito.

**Recomendação**:
- ✅ **Manter delay 0.5s** (seguro, sem bloqueios observados)
- ⚠️ **Poderia testar 0.3s** se quiser acelerar 40% (com monitoramento de bloqueios)
- ❌ **NÃO reduzir para 0.1s** (alto risco de bloqueio)

---

### 2.3 Angeloni (HTML Scraping)

**Plataforma**: VTEX (API bloqueada)
**Discovery**: Sitemap
**Scraping**: Microdata/HTML class-based extraction

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **20** | Conservador para HTML | ✅ **Conservador** |
| `request_delay` | **0.5s** | 2 req/s | ✅ **Conservador** |
| `max_workers` | **1** | Sem paralelização | ✅ **Respeitoso** |

**Estratégias de extração** (fallback em cascata):
1. **Microdata** (schema.org Product) - mais confiável
2. **HTML class-based** (VTEX patterns) - fallback
3. **JavaScript __RUNTIME__** - última tentativa (não implementado ainda)

**Status**: ✅ **Conservador e seguro** - Mesmo perfil que Carrefour (HTML scraping).

**Recomendação**: ✅ **Manter configuração atual** (0.5s delay é seguro).

---

### 2.4 Super Koch (HTML Scraping)

**Plataforma**: Osuper (GraphQL com autenticação)
**Discovery**: Sitemap XML
**Scraping**: JSON-LD extraction from HTML pages

#### Configurações de Performance

| Parâmetro | Valor | Análise | Status |
|-----------|-------|---------|--------|
| `batch_size` | **20** | Conservador para HTML | ✅ **Conservador** |
| `request_delay` | **0.5s** | 2 req/s | ✅ **Conservador** |
| `max_workers` | **1** | Sem paralelização | ✅ **Respeitoso** |

**Status**: ✅ **Conservador e seguro** - Mesmo perfil dos outros HTML scrapers.

---

## 3. Análise Consolidada por Categoria

### 3.1 VTEX API Scrapers

| Store | Regions | Max Workers | Batch Size | Delay | Throughput/Worker | Status |
|-------|---------|-------------|------------|-------|-------------------|--------|
| Bistek | 13 | **13** | 50 | 0.1s | ~10 req/s | ✅ **100%** |
| Fort | 7 | **7** | 50 | 0.1s | ~10 req/s | ✅ **100%** |
| Giassi | 17 | **17** | 50 | 0.1s | ~10 req/s | ✅ **100%** |

**Global Rate Limit**: 5,000 req/min (83 req/s) compartilhado entre todos

**Status Geral**: ✅ **Excelente** - Utilizando 100% da capacidade VTEX com rate limiting thread-safe.

---

### 3.2 HTML Scrapers

| Store | Regions | Max Workers | Batch Size | Delay | Throughput/Worker | Status |
|-------|---------|-------------|------------|-------|-------------------|--------|
| Carrefour | 5 | **1** | 20 | 0.5s | ~2 req/s | ✅ **Conservador** |
| Angeloni | 3 | **1** | 20 | 0.5s | ~2 req/s | ✅ **Conservador** |
| Super Koch | 1 | **1** | 20 | 0.5s | ~2 req/s | ✅ **Conservador** |

**Rate Limit**: N/A (controlado por delay manual)

**Status Geral**: ✅ **Conservador e seguro** - Delay de 0.5s evita bloqueios, sem rate limiting global necessário.

---

## 4. Comparação de Eficiência

### 4.1 Velocidade Relativa

**VTEX API Scrapers** (delay 0.1s):
- **10 req/s** por worker
- **Paralelização**: Sim (múltiplos workers)
- **Eficiência**: ⭐⭐⭐⭐⭐ (máxima)

**HTML Scrapers** (delay 0.5s):
- **2 req/s** por worker
- **Paralelização**: Não (sequential)
- **Eficiência**: ⭐⭐⭐ (conservador, mas seguro)

**Diferença**: VTEX API é **5x mais rápido** que HTML scraping (10 req/s vs 2 req/s).

---

### 4.2 Utilização de Capacidade

#### VTEX Scrapers
- **Capacidade API**: 5,000 req/min (100%)
- **Nossa utilização**: 5,000 req/min (100%) - controlado por rate limiter
- **Utilização**: ✅ **100%** (otimizado ao máximo)

#### HTML Scrapers
- **Capacidade estimada**: Desconhecida (sem rate limit documentado)
- **Nossa utilização**: ~2 req/s (120 req/min)
- **Utilização**: ⚠️ **Conservador** (~20-30% da capacidade estimada?)

**Observação**: HTML scrapers poderiam potencialmente ir mais rápido (0.3s delay = 3.3 req/s), mas priorizamos **segurança** (evitar bloqueios) sobre **velocidade**.

---

## 5. Recomendações Finais

### 5.1 VTEX Scrapers (Bistek, Fort, Giassi)

✅ **Status atual**: **EXCELENTE** - Configuração otimizada ao máximo

**Configuração atual**:
- `batch_size: 50` ✅ (máximo VTEX API)
- `request_delay: 0.1s` ✅ (otimizado recentemente)
- `max_workers: 13/7/17` ✅ (paralelização por região)
- Rate limiter global: ✅ (thread-safe, sliding window)

**Ações**:
- ✅ **Manter configuração atual** (já otimizada)
- ✅ **Monitorar logs** para verificar se rate limiter está bloqueando muito (indica que estamos no limite)
- ℹ️ **Considerar**: Se houver scrapes lentos, verificar se é por bloqueio do rate limiter (normal) ou problemas de rede

---

### 5.2 HTML Scrapers (Carrefour, Angeloni, Super Koch)

✅ **Status atual**: **CONSERVADOR E SEGURO**

**Configuração atual**:
- `batch_size: 20` ✅ (apropriado para HTML)
- `request_delay: 0.5s` ✅ (conservador, sem bloqueios)
- `max_workers: 1` ✅ (sequential, respeitoso)

**Opções de otimização** (em ordem de risco):

1. **Baixo risco** (✅ Recomendado testar):
   - Reduzir delay para `0.3s` (3.3 req/s, +66% de velocidade)
   - Monitorar por 1-2 semanas para verificar bloqueios
   - Se sem bloqueios, manter; senão, voltar para 0.5s

2. **Médio risco** (⚠️ Testar com cautela):
   - Paralelização com `max_workers: 2` (duplica velocidade)
   - Aumenta risco de bloqueio (2x mais requests simultâneas)
   - Monitorar atentamente logs de HTTP 429/403

3. **Alto risco** (❌ NÃO recomendado):
   - Delay < 0.3s (alto risco de bloqueio permanente)
   - `max_workers` > 2 (comportamento "agressivo")

**Ação recomendada**:
- ✅ **Fase 1** (próxima semana): Testar delay 0.3s no Carrefour (menor número de regiões)
- ⏸️ **Fase 2** (se Fase 1 OK): Aplicar 0.3s no Angeloni e Super Koch
- ⏸️ **Fase 3** (se tudo OK): Testar `max_workers: 2` no Carrefour

---

## 6. Métricas de Monitoramento

### 6.1 VTEX Scrapers

**Indicadores de saúde**:
```python
# Verificar estatísticas do rate limiter
rate_limiter.get_stats()
# Output:
# {
#     "current_rate": 83.2,          # req/s atual
#     "requests_in_window": 4992,    # requests nos últimos 60s
#     "rate_limit": 5000,            # limite configurado
#     "max_concurrent": 100,         # concurrent limit
#     "available_concurrent": 87     # slots disponíveis
# }
```

**Alertas**:
- ⚠️ Se `requests_in_window` > 4,500 (90% do limite): Rate limiter está bloqueando muito
- ⚠️ Se `available_concurrent` < 10 (90% ocupado): Muitos workers simultâneos
- ✅ Se `current_rate` ~= 83 req/s: Utilizando 100% da capacidade (ideal!)

---

### 6.2 HTML Scrapers

**Indicadores de saúde**:
```python
# Monitorar logs para HTTP errors
# Indicadores de bloqueio:
# - HTTP 429 (Too Many Requests)
# - HTTP 403 (Forbidden)
# - HTTP 503 (Service Unavailable)
```

**Alertas**:
- ❌ Se HTTP 429 > 1% das requests: Delay muito curto, aumentar para 0.5s
- ❌ Se HTTP 403 frequente: Possível bloqueio de IP/User-Agent
- ⚠️ Se HTTP 5xx > 5%: Servidor sobrecarregado, aumentar delay

---

## 7. Resumo Executivo

| Categoria | Status | Utilização | Ação |
|-----------|--------|------------|------|
| **VTEX API Scrapers** | ✅ **Excelente** | **100%** da capacidade (5,000 req/min) | ✅ Manter |
| **HTML Scrapers** | ✅ **Conservador** | **~30%** da capacidade estimada | ⚠️ Testar 0.3s delay |

**Conclusão**:
- ✅ **VTEX scrapers**: Já otimizados ao máximo (100% da capacidade VTEX com rate limiting seguro)
- ⚠️ **HTML scrapers**: Conservadores (priorizam segurança), mas poderiam ser ~30-40% mais rápidos com delay 0.3s

**Próximos passos**:
1. ✅ Manter VTEX scrapers como estão (já perfeitos)
2. ⚠️ Testar delay 0.3s no Carrefour por 1-2 semanas
3. ℹ️ Monitorar logs para bloqueios (HTTP 429/403)
4. ✅ Se tudo OK, aplicar 0.3s nos outros HTML scrapers

---

**Documentado por**: Alan Lüdke
**Data**: 2026-02-07
**Versão**: 1.0