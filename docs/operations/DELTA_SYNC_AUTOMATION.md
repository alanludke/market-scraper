# Delta Sync Automation Guide

Guia completo para automatizar o delta sync do OpenFoodFacts usando Windows Task Scheduler ou Prefect.

---

## Opção A: Windows Task Scheduler (Recomendado para Windows)

### 1. Scripts Disponíveis

Escolha um dos scripts:

- **Batch**: `scripts/daily_delta_sync.bat` (simples, compatível)
- **PowerShell**: `scripts/daily_delta_sync.ps1` (moderno, com email)

### 2. Configurar Task Scheduler (GUI)

#### Passo 1: Abrir Task Scheduler
1. Pressione `Win + R`
2. Digite: `taskschd.msc`
3. Pressione Enter

#### Passo 2: Criar Tarefa Básica
1. Clique em **"Create Basic Task..."** no painel direito
2. Nome: `Market Scraper - Delta Sync`
3. Descrição: `Daily OpenFoodFacts EAN updates`
4. Clique **Next**

#### Passo 3: Configurar Trigger (Quando executar)
1. Selecione: **Daily**
2. Clique **Next**
3. Hora: `02:00:00` (2:00 AM)
4. Recorrência: `1` dia
5. Clique **Next**

#### Passo 4: Ação (O que executar)
1. Selecione: **Start a program**
2. Clique **Next**
3. **Program/script**:
   - **Batch**: `C:\Users\<seu-user>\Documents\market_scraper\scripts\daily_delta_sync.bat`
   - **PowerShell**: `powershell.exe`
4. **Arguments** (apenas para PowerShell):
   ```
   -ExecutionPolicy Bypass -File "C:\Users\<seu-user>\Documents\market_scraper\scripts\daily_delta_sync.ps1"
   ```
5. **Start in**: `C:\Users\<seu-user>\Documents\market_scraper`
6. Clique **Next**

#### Passo 5: Finalizar
1. Marque: **"Open the Properties dialog..."**
2. Clique **Finish**

#### Passo 6: Configurações Avançadas (Propriedades)
1. Aba **General**:
   - Marque: **"Run whether user is logged on or not"**
   - Marque: **"Run with highest privileges"**
   - Configure for: **Windows 10/11**

2. Aba **Conditions**:
   - **Power**:
     - Desmarque: **"Start the task only if the computer is on AC power"**
     - Marque: **"Wake the computer to run this task"** (opcional)
   - **Network**:
     - Marque: **"Start only if the following network connection is available"**
     - Selecione: **Any connection**

3. Aba **Settings**:
   - Marque: **"Allow task to be run on demand"**
   - Marque: **"Run task as soon as possible after a scheduled start is missed"**
   - **If the task fails, restart every**: `10 minutes` (até 3 tentativas)

4. Clique **OK**
5. Digite sua senha do Windows quando solicitado

### 3. Configurar via PowerShell (Método Avançado)

Execute no PowerShell **como Administrador**:

```powershell
# Definir variáveis
$TaskName = "MarketScraperDeltaSync"
$ScriptPath = "C:\Users\<seu-user>\Documents\market_scraper\scripts\daily_delta_sync.ps1"
$WorkingDir = "C:\Users\<seu-user>\Documents\market_scraper"

# Criar ação
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Criar trigger (diário às 2:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

# Configurações
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10)

# Criar principal (run as SYSTEM ou seu usuário)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

# Registrar tarefa
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Daily OpenFoodFacts delta sync for Market Scraper"

Write-Host "Task Scheduler configurado com sucesso!" -ForegroundColor Green
Write-Host "Você pode testar executando: Start-ScheduledTask -TaskName '$TaskName'"
```

### 4. Testar Execução Manual

```powershell
# Via PowerShell
Start-ScheduledTask -TaskName "MarketScraperDeltaSync"

# Ou via CMD
schtasks /run /tn "MarketScraperDeltaSync"
```

### 5. Ver Logs

```bash
# Ver log mais recente
tail -50 logs\delta_sync_<YYYYMMDD>.log

# Ver todas as execuções
dir logs\delta_sync_*.log
```

### 6. Configurar Email Notifications (Opcional)

Adicione ao seu `.env` ou variáveis de ambiente:

```env
SMTP_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-app
SMTP_FROM=seu-email@gmail.com
SMTP_TO=seu-email@gmail.com
```

**Gmail App Password**: https://myaccount.google.com/apppasswords

---

## Opção B: Prefect (Orquestrador Python)

### 1. Instalar Prefect

```bash
pip install prefect
```

### 2. Criar Flow

Crie `src/orchestration/delta_sync_flow.py`:

```python
from prefect import flow, task
from datetime import timedelta
import subprocess
import logging

logger = logging.getLogger(__name__)

@task(retries=3, retry_delay_seconds=300)
def run_delta_sync():
    """Run OpenFoodFacts delta sync."""
    result = subprocess.run(
        ["python", "cli_enrich.py", "delta-sync"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Delta sync failed: {result.stderr}")
        raise Exception(f"Delta sync failed with code {result.returncode}")

    logger.info(f"Delta sync output: {result.stdout}")
    return result.stdout

@task(retries=2, retry_delay_seconds=60)
def update_dbt_models():
    """Update DBT models after delta sync."""
    result = subprocess.run(
        ["dbt", "run", "--select", "stg_openfoodfacts__products", "dim_ean"],
        cwd="src/transform/dbt_project",
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"DBT update failed: {result.stderr}")
        raise Exception(f"DBT update failed with code {result.returncode}")

    logger.info(f"DBT output: {result.stdout}")
    return result.stdout

@flow(name="daily-delta-sync", log_prints=True)
def daily_delta_sync_flow():
    """Daily flow to sync OpenFoodFacts deltas and update DBT."""
    print("Starting daily delta sync flow...")

    # Run delta sync
    sync_output = run_delta_sync()
    print(f"Delta sync completed: {sync_output[:200]}...")

    # Update DBT models
    dbt_output = update_dbt_models()
    print(f"DBT models updated: {dbt_output[:200]}...")

    print("Daily delta sync flow completed successfully!")

if __name__ == "__main__":
    daily_delta_sync_flow()
```

### 3. Testar Flow

```bash
python src/orchestration/delta_sync_flow.py
```

### 4. Agendar com Prefect

#### Opção 4A: Prefect Cloud (Recomendado)

```bash
# Login no Prefect Cloud
prefect cloud login

# Criar deployment
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 2 * * *" \
    --pool default

# Iniciar worker
prefect worker start --pool default
```

#### Opção 4B: Prefect Server Local

```bash
# Terminal 1: Iniciar Prefect server
prefect server start

# Terminal 2: Criar deployment
prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
    --name daily-delta-sync \
    --cron "0 2 * * *"

# Terminal 3: Iniciar worker
prefect worker start --pool default
```

### 5. Dashboard

- **Prefect Cloud**: https://app.prefect.cloud/
- **Local**: http://localhost:4200/

---

## Opção C: Cron (Linux/WSL)

Se você usar WSL (Windows Subsystem for Linux):

```bash
# Editar crontab
crontab -e

# Adicionar linha (executar diariamente às 2:00 AM)
0 2 * * * cd /path/to/market_scraper && python cli_enrich.py delta-sync && cd src/transform/dbt_project && dbt run --select stg_openfoodfacts__products dim_ean >> /path/to/market_scraper/logs/delta_sync.log 2>&1
```

---

## Monitoramento

### 1. Verificar Última Execução

```bash
# Ver log mais recente
python -c "import json; print(json.dumps(json.load(open('data/metadata/delta_sync_watermark.json')), indent=2))"
```

### 2. Verificar Cobertura EAN

```bash
# Ver estatísticas de enriquecimento
python cli_enrich.py stats

# Query no DuckDB
python -c "import duckdb; conn = duckdb.connect('data/analytics.duckdb'); print(conn.execute('SELECT COUNT(*) as total, SUM(CASE WHEN is_enriched THEN 1 ELSE 0 END) as enriched FROM dev_local.dim_ean').fetchdf())"
```

### 3. Alertas de Falha

Configure alertas no Task Scheduler ou Prefect para notificar em caso de falha:

- **Task Scheduler**: Aba "Settings" > "Send an email" (requer configuração SMTP)
- **Prefect**: Automations > Create Automation > "If flow run fails"

---

## Troubleshooting

### Problema 1: Script não executa

**Solução**:
1. Verifique se Python está no PATH: `python --version`
2. Verifique caminhos absolutos no script
3. Execute manualmente: `scripts\daily_delta_sync.bat`

### Problema 2: Task Scheduler falha

**Solução**:
1. Verifique Event Viewer: `Win + R` → `eventvwr.msc` → Task Scheduler Logs
2. Teste com "Run whether user is logged on or not"
3. Verifique permissões de arquivo

### Problema 3: Delta sync sem novos dados

**Solução**:
1. Verifique watermark: `cat data/metadata/delta_sync_watermark.json`
2. Verifique se deltas estão disponíveis: `curl https://static.openfoodfacts.org/data/delta/index.txt`
3. Execute bulk-import para refresh completo

---

## Recomendações

1. **Frequência**: Execute delta-sync **diariamente** (OpenFoodFacts atualiza diariamente)
2. **Horário**: **2:00 AM** (baixo tráfego, sem impacto nos usuários)
3. **Monitoramento**: Configure alertas de falha (email/Slack)
4. **Backup**: Mantenha logs por 30 dias (`logs/delta_sync_*.log`)
5. **Bulk Refresh**: Execute `bulk-import` **mensalmente** para refresh completo

---

## Próximos Passos

Após configurar automação:
1. ✅ Delta sync rodando diariamente
2. 🔄 Integrar TACO (fonte brasileira) para aumentar coverage
3. 📊 Dashboard de Nutriscore (produtos saudáveis)
4. 🔔 Alertas de hot deals + Nutriscore A/B
