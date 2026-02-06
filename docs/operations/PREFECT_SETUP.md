# Prefect Setup Guide - Market Scraper

Guia completo para configurar Prefect (orquestração local, sem admin).

---

## 🚀 Quick Start (5 minutos)

### **1. Instalar Prefect**

```bash
pip install prefect
```

### **2. Testar Flow Localmente**

```bash
# Rodar flow uma vez (teste)
python src/orchestration/delta_sync_flow.py
```

**Resultado esperado:**
```
==================================================
  Daily Delta Sync Flow - OpenFoodFacts EAN Enrichment
==================================================

[1/2] Starting delta-sync...
OpenFoodFacts Delta Sync
...
✅ Delta sync completed: {...}

[2/2] Updating DBT models...
...
✅ DBT models updated: {...}

==================================================
  Flow Completed Successfully!
==================================================
```

### **3. Configurar Deployment (Agendamento)**

```bash
# Deploy com schedule diário às 9:00 AM
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 9 * * *" \
    --pool default
```

### **4. Iniciar Worker**

Abra um **terminal separado** e deixe rodando:

```bash
# Worker vai processar flows agendados
prefect worker start --pool default
```

**IMPORTANTE:** Deixe este terminal aberto! O worker precisa ficar rodando para executar flows agendados.

---

## 📊 Dashboard (Monitoramento)

### **Opção A: Prefect Cloud** (Recomendado - Gratuito)

```bash
# 1. Criar conta em https://app.prefect.cloud/

# 2. Login
prefect cloud login

# 3. Re-deploy
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 9 * * *" \
    --pool default

# 4. Iniciar worker
prefect worker start --pool default
```

**Dashboard:** https://app.prefect.cloud/

**Recursos:**
- ✅ Histórico de execuções
- ✅ Logs em tempo real
- ✅ Alertas de falha (email)
- ✅ Métricas e gráficos
- ✅ **Gratuito** (até 20k task runs/mês)

### **Opção B: Prefect Server Local**

Terminal 1 - Servidor:
```bash
prefect server start
```

Terminal 2 - Deployment:
```bash
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 9 * * *"
```

Terminal 3 - Worker:
```bash
prefect worker start --pool default
```

**Dashboard Local:** http://localhost:4200/

---

## 🔄 Executar Flows

### **Manual (Teste)**

```bash
# Via CLI
prefect deployment run "daily-delta-sync-flow/daily-delta-sync"

# Ou via Python
python src/orchestration/delta_sync_flow.py
```

### **Automático (Scheduled)**

Após configurar deployment, o flow roda automaticamente no horário agendado (9:00 AM).

**Verificar próxima execução:**
```bash
prefect deployment ls
```

---

## ⚙️ Configurações Avançadas

### **Alterar Horário**

```bash
# Re-deploy com novo horário (diário às 14:00)
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 14 * * *" \
    --pool default
```

**Cron Examples:**
- `0 9 * * *` - 9:00 AM diariamente
- `0 */6 * * *` - A cada 6 horas
- `0 9 * * 1` - 9:00 AM todas segundas-feiras
- `0 9 * * 1-5` - 9:00 AM dias úteis

### **Adicionar Notificações (Email)**

**Via Prefect Cloud:**
1. Dashboard → Automations
2. Create Automation
3. Trigger: "Flow run fails"
4. Action: "Send notification" (email, Slack, PagerDuty)

**Exemplo (YAML):**
```yaml
automation:
  name: Delta Sync Failure Alert
  trigger:
    type: flow_run_state_change
    state: FAILED
  action:
    type: send_email
    to: seu-email@example.com
    subject: "Delta Sync Failed"
```

### **Configurar Timezone**

```bash
# Setar timezone (ambiente)
export TZ="America/Sao_Paulo"

# Ou via Python (delta_sync_flow.py)
import os
os.environ['TZ'] = 'America/Sao_Paulo'
```

---

## 🛠️ Troubleshooting

### **Problema 1: Worker não processa flows**

**Sintoma:** Flow agendado não executa

**Solução:**
1. Verificar se worker está rodando: `prefect worker ls`
2. Verificar pool: `prefect work-pool ls`
3. Restartar worker: `Ctrl+C` → `prefect worker start --pool default`

### **Problema 2: Flow falha com erro de path**

**Sintoma:** `FileNotFoundError` ou `ModuleNotFoundError`

**Solução:**
1. Garantir que `cli_enrich.py` está no diretório raiz do projeto
2. Executar worker a partir do diretório raiz: `cd C:\Users\...\market_scraper`
3. Verificar paths absolutos no flow

### **Problema 3: DBT update falha**

**Sintoma:** Task `update_dbt_models` falha

**Solução:**
1. Verificar se DBT está instalado: `dbt --version`
2. Verificar path do dbt_project: `src/transform/dbt_project`
3. Testar manualmente: `cd src/transform/dbt_project && dbt run --select dim_ean`

### **Problema 4: Worker fecha ao fechar terminal**

**Sintoma:** Worker para quando você fecha o terminal

**Solução (Windows):**

**Opção A: Task Scheduler (sem admin, user logged)**
```powershell
# Criar tarefa que inicia worker ao login
$Action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "-m prefect worker start --pool default" `
    -WorkingDirectory "C:\Users\alan.ludke_indicium\Documents\market_scraper"

$Trigger = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask `
    -TaskName "PrefectWorker" `
    -Action $Action `
    -Trigger $Trigger
```

**Opção B: Startup Folder**
1. Criar arquivo `start_prefect_worker.bat`:
   ```batch
   @echo off
   cd C:\Users\alan.ludke_indicium\Documents\market_scraper
   python -m prefect worker start --pool default
   ```
2. Copiar para: `shell:startup` (Win+R → digitar `shell:startup`)

**Opção C: Screen/tmux (WSL)**
```bash
# Instalar screen (WSL)
sudo apt install screen

# Criar sessão persistente
screen -S prefect
prefect worker start --pool default

# Detach: Ctrl+A → D
# Reattach: screen -r prefect
```

---

## 📈 Monitoramento

### **Ver Execuções Recentes**

```bash
# Listar flow runs
prefect flow-run ls --limit 10

# Ver logs de um run específico
prefect flow-run logs <flow-run-id>
```

### **Ver Estatísticas**

**Via Dashboard:**
- Prefect Cloud: https://app.prefect.cloud/
- Local: http://localhost:4200/

**Via CLI:**
```bash
# Ver deployments
prefect deployment ls

# Ver work pools
prefect work-pool ls

# Ver workers ativos
prefect worker ls
```

### **Logs**

**Prefect armazena logs em:**
- Prefect Cloud: Dashboard → Flow Runs → Logs
- Local Server: `~/.prefect/logs/`

**Logs da aplicação (delta-sync):**
- `logs/delta_sync_YYYYMMDD.log`

---

## 🔐 Boas Práticas

### **1. Usar Prefect Cloud** (Recomendado)

**Vantagens:**
- ✅ Dashboard sempre disponível
- ✅ Logs persistentes (30 dias)
- ✅ Alertas automáticos
- ✅ Não precisa manter servidor local
- ✅ Gratuito (tier básico)

### **2. Manter Worker Rodando**

**Opções:**
- Task Scheduler (ao login)
- Startup folder
- Screen/tmux (WSL)
- Docker container (avançado)

### **3. Configurar Alertas**

Configure notificação de falhas via:
- Email (Prefect Cloud)
- Slack webhook
- Custom webhook (Teams, Discord, etc.)

### **4. Backup de Configurations**

Prefect armazena configs em `~/.prefect/`:
- `profiles.toml` - Perfis de conexão
- `deployments/` - Deployments criados

---

## 🆚 Comparação: Prefect vs Task Scheduler

| Aspecto | Prefect | Task Scheduler |
|---------|---------|----------------|
| **Admin** | ❌ Não precisa | ✅ Precisa (ou roda só quando logado) |
| **Dashboard** | ✅ Visual completo | ❌ GUI básica |
| **Retry** | ✅ Automático (3x) | ⚠️ Manual |
| **Logs** | ✅ Centralizados | ⚠️ Arquivos separados |
| **Alertas** | ✅ Integrados | ⚠️ Precisa configurar SMTP |
| **Setup** | ⚠️ Mais complexo | ✅ Nativo Windows |
| **Manutenção** | ⚠️ Worker sempre rodando | ✅ Zero manutenção |

**Recomendação:** Prefect é melhor para desenvolvimento/staging. Task Scheduler é melhor para produção (se tiver admin).

---

## 📚 Recursos

- **Documentação Oficial:** https://docs.prefect.io/
- **Prefect Cloud:** https://app.prefect.cloud/
- **Exemplos:** https://github.com/PrefectHQ/prefect/tree/main/examples
- **Community:** https://discourse.prefect.io/

---

## ✅ Checklist de Setup

- [ ] `pip install prefect` instalado
- [ ] Flow testado: `python src/orchestration/delta_sync_flow.py`
- [ ] Prefect Cloud configurado (ou server local)
- [ ] Deployment criado: `prefect deploy ...`
- [ ] Worker iniciado: `prefect worker start --pool default`
- [ ] Worker persistente (Task Scheduler / Startup folder)
- [ ] Alertas configurados (email/Slack)
- [ ] Dashboard acessível e monitorado

---

**Status:** 🟢 Pronto para Produção (sem admin!)

