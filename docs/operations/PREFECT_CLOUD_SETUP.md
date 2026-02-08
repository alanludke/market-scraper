# Guia Completo - Prefect Cloud Setup

## 🎯 Objetivo

Migrar do Prefect local para **Prefect Cloud (Free Tier)** com as otimizações implementadas.

---

## ⚡ Quick Start (5 minutos)

```bash
# 1. Login no Prefect Cloud (abre navegador)
prefect cloud login

# 2. Criar work pool
prefect work-pool create market-scraper-pool --type process

# 3. Deploy dos flows (PowerShell)
.\deploy_to_cloud.ps1

# 4. Iniciar worker (manter rodando)
prefect worker start --pool market-scraper-pool
```

**Pronto!** Dashboard em: https://app.prefect.cloud

---

## 📋 Passo a Passo Detalhado

### **Passo 1: Login no Prefect Cloud** 🔐

```bash
prefect cloud login
```

**O que acontece**:
1. Navegador abre automaticamente
2. Crie conta (email + senha) ou faça login com Google/GitHub
3. Autorize o CLI (clique em "Authorize")
4. Selecione workspace ou crie um novo

**Verificar conexão**:
```bash
prefect config view
# Deve mostrar: PREFECT_API_URL='https://api.prefect.cloud/...'
```

---

### **Passo 2: Criar Work Pool** 🏊

```bash
# Criar pool para executar os scrapers
prefect work-pool create market-scraper-pool --type process

# Verificar que foi criado
prefect work-pool ls
```

**O que é Work Pool?**
- Grupo de workers que executam tasks
- Workers rodam **localmente** (sua máquina)
- Conectam no Prefect Cloud para buscar trabalho

---

### **Passo 3: Deploy dos Flows** 🚀

#### Opção A: Script Automatizado (Recomendado)

**PowerShell**:
```powershell
.\deploy_to_cloud.ps1
```

**Bash/Linux**:
```bash
bash deploy_to_cloud.sh
```

#### Opção B: Deploy Manual

```bash
# Flow diário incremental (padrão - rápido!)
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow \
    --name daily-scraper-incremental \
    --pool market-scraper-pool \
    --cron "0 2 * * *" \
    --param use_incremental=true \
    --param incremental_days=7

# Flow mensal full (catálogo completo)
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow \
    --name monthly-scraper-full \
    --pool market-scraper-pool \
    --cron "0 3 1 * *" \
    --param use_incremental=false
```

**Verificar deploys**:
```bash
prefect deployment ls
```

---

### **Passo 4: Iniciar Worker** 🏃

```bash
# Iniciar worker (manter rodando)
prefect worker start --pool market-scraper-pool
```

**IMPORTANTE**: O worker precisa ficar rodando para executar os flows!

**Dicas**:
- Deixe rodando em terminal separado
- Ou rode em background (próxima seção)

---

## 🔄 **Rodando Worker em Background**

### **Opção 1: PowerShell (Windows)**

```powershell
# Iniciar worker em background
Start-Process -FilePath "prefect" `
    -ArgumentList "worker start --pool market-scraper-pool" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "data/logs/prefect_worker.log" `
    -RedirectStandardError "data/logs/prefect_worker_error.log"
```

### **Opção 2: nssm (Windows Service)**

```bash
# Instalar nssm (se não tiver)
choco install nssm

# Criar serviço Windows
nssm install PrefectWorker "prefect" "worker start --pool market-scraper-pool"
nssm set PrefectWorker AppDirectory "C:\Users\...\market_scraper"
nssm start PrefectWorker

# Verificar status
nssm status PrefectWorker
```

### **Opção 3: Linux/Mac (systemd ou screen)**

```bash
# Usando screen
screen -dmS prefect-worker prefect worker start --pool market-scraper-pool

# Verificar
screen -ls

# Reconectar
screen -r prefect-worker
```

---

## 📊 **Flows Deployados**

| Flow | Frequência | Modo | Descrição |
|------|-----------|------|-----------|
| **daily-scraper-incremental** | Diário (2 AM) | Incremental (7d) | Scraping rápido (30-60 min) |
| **monthly-scraper-full** | Mensal (dia 1, 3 AM) | Full catalog | Refresh completo (2.7h) |
| **daily-delta-sync** | Diário (9 AM) | Incremental | Sync OpenFoodFacts |

---

## 🧪 **Testar Flows**

### **Teste Manual (Via CLI)**

```bash
# Executar flow incremental agora (não esperar cron)
prefect deployment run daily-scraper-incremental/daily-scraper-incremental

# Executar flow full agora
prefect deployment run monthly-scraper-full/monthly-scraper-full
```

### **Teste Manual (Via Dashboard)**

1. Acesse https://app.prefect.cloud
2. Vá em "Deployments"
3. Clique em "daily-scraper-incremental"
4. Clique em "Run" → "Quick Run"
5. Acompanhe em "Flow Runs"

---

## 📈 **Monitoramento**

### **Dashboard**

https://app.prefect.cloud

**O que você vê**:
- ✅ Flow runs (sucessos/falhas)
- ⏱️ Duração de cada run
- 📊 Logs em tempo real
- 📧 Histórico completo

### **Notificações**

Configure alertas de falha:

1. Dashboard → "Notifications"
2. "Create Notification"
3. Escolha:
   - Trigger: "Flow run fails"
   - Flows: "daily-scraper-incremental"
   - Channel: Email/Slack/Webhook

### **Métricas**

```bash
# Via CLI
prefect flow-run ls --limit 10

# Ver logs de uma run específica
prefect flow-run logs <flow-run-id>
```

---

## 🎛️ **Configurações Úteis**

### **Parâmetros Customizados**

Para rodar com parâmetros diferentes:

```bash
# Incremental de 14 dias (em vez de 7)
prefect deployment run daily-scraper-incremental/daily-scraper-incremental \
    --param incremental_days=14

# Apenas uma loja
prefect deployment run daily-scraper-incremental/daily-scraper-incremental \
    --param stores='["angeloni"]'
```

### **Pausar/Despausar Schedules**

```bash
# Pausar schedule (não executará no cron)
prefect deployment pause daily-scraper-incremental/daily-scraper-incremental

# Despausar
prefect deployment resume daily-scraper-incremental/daily-scraper-incremental
```

---

## 🔧 **Troubleshooting**

### **Worker não conecta**

```bash
# Verificar conexão
prefect config view

# Se API URL não for Cloud, refazer login
prefect cloud login
```

### **Flow não executa**

1. Verificar que worker está rodando:
   ```bash
   prefect work-pool get-default-queue market-scraper-pool
   ```

2. Ver logs do worker:
   ```bash
   tail -f data/logs/prefect_worker.log
   ```

### **Rate Limiting (HTTP 429)**

Se logs mostrarem erro 429:

1. Edite `config/stores.yaml`:
   ```yaml
   request_delay: 0.2  # aumentar de 0.1
   ```

2. Redeploy:
   ```bash
   .\deploy_to_cloud.ps1
   ```

---

## 💰 **Limites do Free Tier**

| Recurso | Free Tier | Seu Uso Estimado |
|---------|-----------|------------------|
| **Task runs/mês** | 10,000 | ~3,000 (muito abaixo!) |
| **Flow runs/mês** | Ilimitado | ~90 (3/dia) |
| **Users** | 1 | 1 ✅ |
| **Retention** | 7 dias | Suficiente ✅ |
| **Workers** | Ilimitado | 1 ✅ |

**Conclusão**: Você está **bem abaixo** do limite! 😎

---

## 🚀 **Próximos Passos**

1. ✅ Setup Prefect Cloud (seguir este guia)
2. 🧪 Testar flow incremental manualmente
3. 📊 Monitorar primeira execução automática (cron)
4. 📧 Configurar notificações de erro
5. 🎉 Deixar rodando automaticamente!

---

## 📚 **Recursos**

- **Dashboard**: https://app.prefect.cloud
- **Docs Prefect Cloud**: https://docs.prefect.io/cloud/
- **Planos**: https://www.prefect.io/pricing (Free = $0 forever!)
- **Status Page**: https://status.prefect.io/

---

## 🆘 **Ajuda**

### **Comandos Úteis**

```bash
# Ver todos os deployments
prefect deployment ls

# Ver flow runs recentes
prefect flow-run ls --limit 10

# Ver logs de uma run
prefect flow-run logs <flow-run-id>

# Ver workers ativos
prefect worker ls

# Health check
prefect cloud workspace ls
```

### **Links Rápidos**

- Logs locais: `data/logs/`
- Configurações: `config/stores.yaml`
- Flow code: `src/orchestration/scraper_flow.py`
- Guia de otimizações: `OPTIMIZATION_GUIDE.md`

---

**Última atualização**: 2026-02-07
**Versão**: 1.0 (Prefect Cloud Migration)
