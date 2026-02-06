# 🔐 Authentication Guide

## Quick Start (2 minutos)

### 1. Ativar Autenticação

Adicione **UMA LINHA** no início do `src/dashboard/app.py`:

```python
# src/dashboard/app.py
import streamlit as st
from src.dashboard.utils.auth import require_authentication

# 👇 ADD THIS LINE
require_authentication()

# Rest of your code...
st.set_page_config(...)
```

### 2. Configurar Senha no Streamlit Cloud

1. Vá para seu app: https://share.streamlit.io/
2. Clique no app → **Settings** → **Secrets**
3. Adicione:

```toml
password = "indicium2026"
```

4. Save → Deploy

**Pronto!** Agora o dashboard requer senha para acessar.

---

## Funcionalidades

### Login Screen

Quando não autenticado, usuário vê:

```
🔐 Market Scraper - Login
━━━━━━━━━━━━━━━━━━━━━━━━━
       [Password Input]
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Market Scraper Dashboard
```

### Logout (Opcional)

Adicione botão de logout na sidebar:

```python
# src/dashboard/app.py
from src.dashboard.utils.auth import require_authentication, logout

require_authentication()

# Add logout button
if st.sidebar.button("🚪 Logout"):
    logout()

# Rest of your app...
```

---

## Opções Avançadas

### Opção 1: Múltiplos Usuários (Google Sheets)

**1. Crie Google Sheet com usuários:**

| email | password | role |
|-------|----------|------|
| alan@indicium.tech | senha123 | admin |
| user@indicium.tech | user456 | viewer |

**2. Compartilhe como "Anyone with the link can view"**

**3. Pegue o link de compartilhamento CSV:**
```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0
```

**4. Configure nos Secrets:**
```toml
google_sheets_url = "https://docs.google.com/spreadsheets/d/..."
```

**5. Modifique `auth.py`:**
```python
import pandas as pd

@st.cache_data(ttl=300)
def load_users():
    sheet_url = st.secrets["google_sheets_url"]
    return pd.read_csv(sheet_url)

def check_password():
    users = load_users()

    email = st.text_input("📧 Email")
    password = st.text_input("🔐 Password", type="password")

    if st.button("Login"):
        user = users[(users['email'] == email) & (users['password'] == password)]
        if not user.empty:
            st.session_state["password_correct"] = True
            st.session_state["user_email"] = email
            st.session_state["user_role"] = user.iloc[0]['role']
            st.rerun()
        else:
            st.error("❌ Email ou senha inválidos")

    return st.session_state.get("password_correct", False)
```

### Opção 2: SSO com Google (Pago - Teams Plan)

Requer Streamlit Teams ($50/mês):
- Login com Google automático
- Configuração via dashboard (zero código)
- SAML/OIDC para empresas

---

## Segurança Best Practices

### ✅ DO

- Use senhas fortes (mínimo 12 caracteres)
- Armazene senhas APENAS em Streamlit Secrets (nunca no código)
- Use HTTPS (Streamlit Cloud já tem SSL)
- Adicione timeout de sessão se necessário

### ❌ DON'T

- Não commite senhas no Git
- Não use `password = "123456"` no código
- Não compartilhe URL do dashboard publicamente se sensível

---

## Testing Locally

Para testar autenticação localmente:

**1. Crie `.streamlit/secrets.toml` (NÃO commitar!):**
```toml
password = "test123"
```

**2. Adicione ao `.gitignore`:**
```
.streamlit/secrets.toml
```

**3. Run:**
```bash
streamlit run app.py
```

---

## Deployment Checklist

- [ ] `require_authentication()` adicionado no app.py
- [ ] Senha configurada em Streamlit Secrets
- [ ] `.streamlit/secrets.toml` no .gitignore (para dev local)
- [ ] Testado localmente
- [ ] Deployed no Streamlit Cloud
- [ ] Senha testada no app deployado

---

## FAQ

### Como mudar a senha?

Streamlit Cloud → App Settings → Secrets → Editar → Save → Redeploy

### Senha funciona em páginas (pages/)?

Sim! `require_authentication()` protege TODO o app, incluindo páginas.

### Posso ter diferentes senhas por página?

Sim, chame `check_password()` com diferentes secrets por página:

```python
# pages/admin.py
if not check_admin_password():
    st.stop()
```

### Como adicionar timeout de sessão?

```python
import time

def require_authentication():
    if not check_password():
        st.stop()

    # Add timeout (30 minutes)
    if "login_time" not in st.session_state:
        st.session_state["login_time"] = time.time()

    if time.time() - st.session_state["login_time"] > 1800:  # 30 min
        st.warning("⏰ Sessão expirada. Faça login novamente.")
        logout()
```

---

**Última atualização**: 2026-02-06
