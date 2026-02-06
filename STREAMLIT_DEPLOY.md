# Streamlit Cloud Deployment Guide

## 📋 Pré-requisitos

1. Conta no [Streamlit Cloud](https://streamlit.io/cloud)
2. Repositório GitHub com código atualizado
3. Arquivo `analytics.duckdb` disponível (gerado pelo DBT)

---

## 🚀 Deploy no Streamlit Cloud

### Opção 1: Deploy Direto (Recomendado para Desenvolvimento)

1. Acesse [share.streamlit.io](https://share.streamlit.io/)
2. Clique em **"New app"**
3. Preencha:
   - **Repository**: `alanludke/market-scraper`
   - **Branch**: `master`
   - **Main file path**: `app.py`
4. **Advanced settings**:
   - Python version: `3.11`
   - Requirements file: `requirements_dashboard.txt`
5. Clique em **"Deploy!"**

### Opção 2: Deploy via CLI

```bash
# Instalar Streamlit CLI
pip install streamlit

# Login
streamlit login

# Deploy
streamlit deploy app.py
```

---

## 📁 Estrutura de Arquivos Necessários

```
market-scraper/
├── app.py                          # Entry point do dashboard
├── requirements_dashboard.txt      # Dependências Python
├── .streamlit/
│   └── config.toml                # Configuração do Streamlit
├── src/dashboard/
│   ├── app.py                     # App principal
│   └── pages/                     # Páginas do dashboard
│       ├── 1_💰_Análise_de_Preços.py
│       ├── 2_🏷️_Análise_de_Promoções.py
│       └── 3_🥊_Competitividade.py
└── data/
    └── analytics.duckdb           # Banco de dados (precisa estar disponível!)
```

---

## ⚙️ Configuração do Banco de Dados

### Problema: analytics.duckdb não está no Git

O arquivo `data/analytics.duckdb` (143MB) **não deve** ser commitado no Git (muito grande).

**Soluções:**

### 1. **Google Drive / Dropbox** (Simples)

```python
# src/dashboard/app.py
import streamlit as st
import duckdb
from pathlib import Path
import requests

@st.cache_resource
def get_conn():
    db_path = Path("data/analytics.duckdb")

    # Se não existe, baixar do Google Drive
    if not db_path.exists():
        db_path.parent.mkdir(exist_ok=True)
        url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
        st.info("Baixando banco de dados... (somente primeira vez)")
        response = requests.get(url)
        db_path.write_bytes(response.content)

    return duckdb.connect(str(db_path), read_only=True)
```

### 2. **GitHub LFS** (Large File Storage)

```bash
# Instalar Git LFS
git lfs install

# Rastrear arquivo grande
git lfs track "data/analytics.duckdb"

# Commit
git add .gitattributes data/analytics.duckdb
git commit -m "Add analytics.duckdb via LFS"
git push
```

**Nota**: Streamlit Cloud tem suporte a Git LFS, mas há limites de storage (1GB grátis).

### 3. **DuckDB Cloud / MotherDuck** (Produção)

```python
import duckdb

conn = duckdb.connect('md:my_database')  # MotherDuck cloud database
```

**Vantagens**:
- Banco 100% na nuvem
- Sem download necessário
- Atualização automática

**Como usar**:
1. Criar conta em [motherduck.com](https://motherduck.com/)
2. Fazer upload do `analytics.duckdb`
3. Conectar via token de acesso

### 4. **Rebuild On-Demand** (Ideal)

```python
# Se analytics.duckdb não existe, rodar DBT
if not Path("data/analytics.duckdb").exists():
    st.info("Reconstruindo banco de dados...")
    os.system("cd src/transform/dbt_project && dbt run")
```

**Desvantagem**: Requer dados bronze (também grandes).

---

## 🔐 Secrets Management

Para configurar segredos (API keys, database URLs):

1. No Streamlit Cloud, vá em **Settings → Secrets**
2. Adicione secrets em formato TOML:

```toml
[motherduck]
token = "eyJhbGci..."

[azure]
connection_string = "DefaultEndpointsProtocol=..."
```

3. Acesse no código:

```python
import streamlit as st

motherduck_token = st.secrets["motherduck"]["token"]
```

---

## 📊 Testando Localmente

```bash
# Instalar dependências
pip install -r requirements_dashboard.txt

# Rodar localmente
streamlit run app.py

# Acessar em http://localhost:8501
```

---

## ✅ Checklist de Deploy

- [ ] `requirements_dashboard.txt` atualizado
- [ ] `.streamlit/config.toml` configurado
- [ ] `app.py` na raiz do projeto
- [ ] Banco `analytics.duckdb` acessível (via download, LFS, ou cloud)
- [ ] Secrets configurados (se necessário)
- [ ] Testado localmente
- [ ] Repositório GitHub atualizado
- [ ] Deploy no Streamlit Cloud

---

## 🐛 Troubleshooting

### Erro: "DuckDB database not found"

**Solução**: Implementar download automático do banco (ver opções acima).

### Erro: "Module not found"

**Solução**: Verificar se `requirements_dashboard.txt` tem todas as dependências.

### Erro: "Permission denied"

**Solução**: Streamlit Cloud tem permissões limitadas. Use `read_only=True` para DuckDB.

### App lento no primeiro acesso

**Solução**: Normal! O Streamlit Cloud faz "cold start". Use `@st.cache_resource` para cache.

---

## 📈 Próximos Passos

1. ✅ Deploy básico funcionando
2. [ ] Configurar auto-update do banco (webhook do DBT)
3. [ ] Adicionar autenticação (Streamlit Auth)
4. [ ] Custom domain (app.market-scraper.com)
5. [ ] Monitoramento de uso (Google Analytics)

---

**Última atualização**: 2026-02-06
**Deploy URL** (após deploy): `https://market-scraper.streamlit.app/`
