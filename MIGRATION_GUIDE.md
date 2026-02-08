# Guia de Migração - Dados Legados

Este guia explica como migrar os dados do `/archive` para a estrutura atual do projeto.

## Visão Geral

O script de migração (`scripts/migrate_legacy_data.py`) converte dados JSONL legados para Parquet com:

✅ **Validação de schema** - Valida todos os registros contra `VTEXProduct` (Pydantic)
✅ **Limpeza de dados** - Normaliza campos (preços, EANs, etc.)
✅ **Deduplicação** - Remove duplicatas por `product_id + scraped_at`
✅ **Compressão** - Converte JSONL → Parquet (redução de ~80-90%)
✅ **Estrutura correta** - Segue naming convention atual (`run_{store}_{timestamp}`)

## Estrutura

### Origem (Archive)
```
archive/legacy_scrapers/
├── bistek_products_scraper/
│   └── data/bronze/supermarket=bistek/region=balneario_camboriu/
│       └── year=2026/month=01/day=25/run_20260125_161503/
│           └── bistek_balneario_camboriu_full.jsonl
├── fort_products_scraper/
└── giassi_products_scraper/
```

### Destino (Bronze)
```
data/bronze/
└── supermarket=bistek/region=balneario_camboriu/
    └── year=2026/month=01/day=25/
        └── run_bistek_20260125_161503.parquet
```

## Como Usar

### 1. Dry Run (Testar sem escrever)

Recomendado para verificar quantos registros serão migrados:

```bash
# Testar uma loja
python scripts/migrate_legacy_data.py --store bistek --dry-run

# Testar todas as lojas
python scripts/migrate_legacy_data.py --store all --dry-run
```

### 2. Migração com Filtro de Data

Migrar apenas dados de um período específico:

```bash
# Migrar dados de Janeiro/2026
python scripts/migrate_legacy_data.py \
    --store bistek \
    --start-date 2026-01-25 \
    --end-date 2026-01-31

# Migrar tudo até uma data
python scripts/migrate_legacy_data.py \
    --store all \
    --end-date 2026-02-01
```

### 3. Migração Completa

Migrar **todos** os dados de todas as lojas:

```bash
# ⚠️ ATENÇÃO: Isso processará ~138 arquivos JSONL (~12GB)
python scripts/migrate_legacy_data.py --store all
```

### 4. Migração por Loja

Migrar uma loja específica:

```bash
# Bistek (múltiplas regiões)
python scripts/migrate_legacy_data.py --store bistek

# Fort (Florianópolis)
python scripts/migrate_legacy_data.py --store fort

# Giassi (múltiplas lojas)
python scripts/migrate_legacy_data.py --store giassi
```

## O Que o Script Faz

### 1. Leitura e Validação
```python
# Lê JSONL linha por linha
for line in jsonl_file:
    record = json.loads(line)

    # Valida com Pydantic schema
    product = VTEXProduct.parse_obj(record)

    # Registros inválidos são descartados e contabilizados
```

### 2. Limpeza e Normalização
```python
# VTEXProduct schema normaliza:
# - Preços (Decimal)
# - EANs (string, leading zeros)
# - Timestamps (datetime)
# - product_id (string)
# - Campos opcionais (None se ausente)
```

### 3. Deduplicação
```python
# Remove duplicatas por chave composta
df.drop_duplicates(subset=["product_id", "scraped_at"], keep="first")
```

### 4. Conversão para Parquet
```python
df.to_parquet(
    output_file,
    engine="pyarrow",
    compression="snappy",  # Compressão rápida e eficiente
    index=False
)
```

## Estatísticas de Saída

O script exibe estatísticas detalhadas:

```
============================================================
MIGRATION SUMMARY
============================================================
Files processed: 138
Files skipped: 2
Records total: 1,234,567
Records migrated: 1,200,000
Records invalid: 34,567  (2.8%)
Records duplicated: 0
Errors: 0
Success rate: 97.2%
============================================================
```

### Logs Detalhados

Logs salvos em `data/logs/migration_{timestamp}.log`:

```json
{
  "time": "2026-02-08 14:30:00",
  "level": "INFO",
  "message": "Processing: bistek_balneario_camboriu_full.jsonl"
}
{
  "time": "2026-02-08 14:30:05",
  "level": "INFO",
  "message": "Read 12,345 records"
}
{
  "time": "2026-02-08 14:30:10",
  "level": "INFO",
  "message": "Valid records: 12,100/12,345"
}
```

## Validação de Schema (VTEXProduct)

O script valida os seguintes campos obrigatórios:

| Campo | Tipo | Validação |
|-------|------|-----------|
| `product_id` | string | Obrigatório, não vazio |
| `product_name` | string | Obrigatório, não vazio |
| `brand` | string | Obrigatório |
| `ean` | string | Obrigatório, 13 dígitos |
| `price` | Decimal | > 0 |
| `list_price` | Decimal | ≥ price |
| `available` | bool | true/false |
| `category_id` | string | Obrigatório |
| `link` | AnyUrl | URL válida |
| `image_url` | AnyUrl | URL válida |
| `scraped_at` | datetime | ISO 8601 |

**Registros inválidos** são descartados e contabilizados em `records_invalid`.

## Tratamento de Erros

### Erro: "Legacy directory not found"
```bash
# Verificar se o diretório existe
ls archive/legacy_scrapers/

# Solução: Verifique se o archive foi extraído corretamente
```

### Erro: "No valid records after validation"
```bash
# Arquivo JSONL corrompido ou schema incompatível
# Solução: Verificar logs detalhados em data/logs/migration_*.log
```

### Erro: "Invalid JSON line"
```bash
# Linha corrompida no JSONL
# Solução: Script pula linhas inválidas automaticamente
```

## Verificação Pós-Migração

### 1. Verificar arquivos Parquet criados
```bash
# Contar arquivos Parquet
find data/bronze -name "*.parquet" | wc -l

# Verificar tamanho total
du -sh data/bronze
```

### 2. Testar leitura com DuckDB
```bash
python -c "
import duckdb
con = duckdb.connect()
print(con.execute('''
    SELECT
        COUNT(*) as total_products,
        COUNT(DISTINCT product_id) as unique_products,
        MIN(scraped_at) as first_scrape,
        MAX(scraped_at) as last_scrape
    FROM read_parquet(\"data/bronze/**/*.parquet\")
''').fetchall())
"
```

### 3. Executar DBT para processar bronze → silver
```bash
cd src/transform/dbt_project

# Processar staging (bronze → silver)
dbt run --select staging.*

# Verificar dados
dbt test --select staging.*
```

## Limpeza do Archive

⚠️ **ATENÇÃO**: Apenas delete o `/archive` **APÓS** confirmar que:

1. ✅ Migração completa sem erros
2. ✅ DBT processou dados com sucesso
3. ✅ Dashboards funcionando com novos dados
4. ✅ Backup do archive em local seguro (se necessário)

```bash
# Fazer backup do archive (opcional)
tar -czf archive_backup_$(date +%Y%m%d).tar.gz archive/

# Verificar tamanho do backup
ls -lh archive_backup_*.tar.gz

# Deletar archive (irreversível!)
rm -rf archive/
```

## Comparação: Antes vs Depois

### Antes (Archive JSONL)
- 📁 138 arquivos JSONL
- 💾 12 GB de dados
- ❌ Sem validação de schema
- ❌ Registros duplicados
- ❌ Campos inconsistentes
- ⏱️ Queries lentas (60s+)

### Depois (Bronze Parquet)
- 📁 138 arquivos Parquet
- 💾 ~1.2 GB de dados (90% redução)
- ✅ Schema validado (VTEXProduct)
- ✅ Dados deduplicados
- ✅ Campos normalizados
- ⚡ Queries rápidas (<2s)

## Troubleshooting

### Progress Bar não aparece
```bash
# Instalar tqdm
pip install tqdm
```

### Erro de import VTEXProduct
```bash
# Instalar dependências
pip install -r requirements.txt

# Verificar se src/ está no PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Espaço em disco insuficiente
```bash
# Verificar espaço disponível
df -h

# Limpar arquivos temporários
rm -rf data/logs/migration_*.log
```

## FAQ

**Q: Preciso migrar tudo de uma vez?**
A: Não. Você pode migrar por loja ou por período de data.

**Q: Os dados originais são modificados?**
A: Não. O script apenas **lê** do `/archive` e **escreve** em `data/bronze/`.

**Q: Posso rodar a migração múltiplas vezes?**
A: Sim, mas arquivos duplicados sobrescreverão os anteriores (mesmo `run_id`).

**Q: O que acontece com registros inválidos?**
A: São descartados e contabilizados em `records_invalid` nas estatísticas.

**Q: Preciso rodar DBT depois?**
A: Sim! A migração apenas move para bronze. DBT processa bronze → silver → gold.

**Q: Posso cancelar a migração?**
A: Sim (Ctrl+C). Arquivos já migrados permanecerão em `data/bronze/`.

## Próximos Passos

Após a migração:

1. **Executar DBT** para processar os dados migrados:
   ```bash
   cd src/transform/dbt_project
   dbt run --select staging.*
   dbt run --select trusted.*
   dbt run --select marts.*
   ```

2. **Validar qualidade** com Great Expectations:
   ```bash
   great_expectations checkpoint run bronze_checkpoint
   ```

3. **Testar dashboards** com os novos dados:
   ```bash
   streamlit run src/dashboard/app.py
   ```

4. **Fazer backup e deletar archive** (opcional):
   ```bash
   tar -czf archive_backup.tar.gz archive/
   rm -rf archive/
   ```

---

**Última atualização**: 2026-02-08
**Autor**: Market Scraper Team
