# Consolidação de Localizações - dim_location

## 🎯 Problema Atual

### Identificadores Não Padronizados

Atualmente, os identificadores de região em `config/stores.yaml` **não são únicos globalmente** - apenas dentro de cada loja:

```yaml
bistek:
  regions:
    florianopolis_costeira:  # ID: florianopolis_costeira
      cep: "88047-010"

fort:
  regions:
    florianopolis_costeira:  # ID: florianopolis_costeira (MESMO ID, LOCAL DIFERENTE!)
      cep: "88047-010"

giassi:
  regions:
    florianopolis_santa_monica:  # ID: florianopolis_santa_monica
      cep: "88035-000"
    florianopolis_sacogrande:    # ID: florianopolis_sacogrande
      cep: "88032-005"
```

**Problemas:**

1. **Não há consolidação geográfica**: Não conseguimos comparar preços de lojas diferentes no **mesmo bairro**
2. **IDs ambíguos**: `florianopolis_costeira` pode ser Bistek OU Fort (locais diferentes!)
3. **Hierarquia quebrada**: Não temos cidade → bairro → loja de forma normalizada
4. **Análise geoespacial impossível**: Sem lat/long, não podemos fazer mapas de calor

---

## 💡 Solução Proposta

### Arquitetura de 3 Camadas

```
┌─────────────────┐
│   dim_location  │  ← Consolidação de localizações únicas (independente de lojas)
└────────┬────────┘
         │
         │ many-to-many
         │
┌────────▼────────────────┐
│ dim_store_location      │  ← Associação loja ↔ localização
└────────┬────────────────┘
         │
         │ FK
         │
┌────────▼────────┐
│    dim_store    │  ← Lojas (Bistek, Fort, Giassi)
└─────────────────┘
```

### 1. `dim_location` (Conformed Dimension)

Localização **única** independente de loja:

```sql
CREATE TABLE dim_location (
    location_key INTEGER PRIMARY KEY,           -- Surrogate key
    location_id VARCHAR UNIQUE NOT NULL,        -- Natural key (florianopolis_costeira)

    -- Hierarquia geográfica
    city_name VARCHAR NOT NULL,                 -- Florianópolis
    city_code VARCHAR,                          -- SC-FLN (IBGE code)
    neighborhood_name VARCHAR,                  -- Costeira do Pirajubaé
    neighborhood_code VARCHAR NOT NULL,         -- costeira

    -- Geolocalização
    cep VARCHAR NOT NULL,                       -- 88047-010
    latitude DECIMAL(9,6),                      -- -27.5969 (para mapas)
    longitude DECIMAL(9,6),                     -- -48.5494

    -- Metadata
    state_code VARCHAR NOT NULL DEFAULT 'SC',   -- SC, RS
    country_code VARCHAR NOT NULL DEFAULT 'BR',
    last_updated TIMESTAMP DEFAULT NOW()
);
```

**Exemplo de dados:**

| location_key | location_id | city_name | neighborhood_code | cep | latitude | longitude |
|--------------|-------------|-----------|-------------------|-----|----------|-----------|
| 1 | florianopolis_costeira | Florianópolis | costeira | 88047-010 | -27.5969 | -48.5494 |
| 2 | florianopolis_santa_monica | Florianópolis | santa_monica | 88035-000 | -27.5877 | -48.5321 |
| 3 | tubarao_oficinas | Tubarão | oficinas | 88701-000 | -28.4665 | -49.0076 |

### 2. `dim_store_location` (Bridge Table)

Associação many-to-many entre lojas e localizações:

```sql
CREATE TABLE dim_store_location (
    store_location_key INTEGER PRIMARY KEY,    -- Surrogate key
    store_key INTEGER NOT NULL,                -- FK → dim_store
    location_key INTEGER NOT NULL,             -- FK → dim_location

    -- Dados específicos da loja nessa localização
    store_address VARCHAR,                     -- Endereço completo da loja
    hub_id VARCHAR,                            -- VTEX hub_id (v2.1E10CE150...)
    sc_code VARCHAR,                           -- Sales channel (1, 2, 3...)

    -- Operational metadata
    is_active BOOLEAN DEFAULT TRUE,            -- Loja ainda opera nessa localização?
    opened_at DATE,                            -- Data de inauguração
    closed_at DATE,                            -- Data de fechamento (se aplicável)

    FOREIGN KEY (store_key) REFERENCES dim_store(store_key),
    FOREIGN KEY (location_key) REFERENCES dim_location(location_key)
);
```

**Exemplo de dados:**

| store_location_key | store_key | location_key | hub_id | store_address |
|--------------------|-----------|--------------|--------|---------------|
| 1 | 1 (Bistek) | 1 (florianopolis_costeira) | v2.1E10CE150... | Av. Gov. Ivo Silveira, 2445 |
| 2 | 2 (Fort) | 1 (florianopolis_costeira) | v2.1BB18CE648... | Rod. SC-401, km 5 |
| 3 | 3 (Giassi) | 2 (florianopolis_santa_monica) | NULL | R. José Cândido da Silva, 78 |

**Vantagem:** Bistek e Fort podem ter lojas na **mesma localização** (`florianopolis_costeira`), mas em endereços diferentes!

### 3. Atualizar `fct_daily_prices`

Substituir `region_key` por `location_key`:

```sql
ALTER TABLE fct_daily_prices
ADD COLUMN location_key INTEGER REFERENCES dim_location(location_key);

-- Migração de dados
UPDATE fct_daily_prices dp
SET location_key = sl.location_key
FROM dim_store_location sl
WHERE dp.store_key = sl.store_key
  AND dp.region_key = sl.legacy_region_key;  -- Mapeamento temporário
```

---

## 📊 Casos de Uso Desbloqueados

### 1. Comparação de Preços no Mesmo Bairro

```sql
-- Comparar preços de Bistek vs Fort na Costeira
SELECT
    l.neighborhood_name,
    s.store_name,
    p.product_name,
    p.min_price
FROM fct_daily_prices p
JOIN dim_store s ON p.store_key = s.store_key
JOIN dim_location l ON p.location_key = l.location_key
WHERE l.location_id = 'florianopolis_costeira'
ORDER BY p.product_name, p.min_price;
```

### 2. Análise Geoespacial (Mapas de Calor)

```python
import plotly.express as px

# Preço médio por localização
prices_by_location = conn.execute("""
    SELECT
        l.latitude,
        l.longitude,
        l.neighborhood_name,
        AVG(p.min_price) as avg_price
    FROM fct_daily_prices p
    JOIN dim_location l ON p.location_key = l.location_key
    GROUP BY l.latitude, l.longitude, l.neighborhood_name
""").df()

# Mapa de calor de preços
fig = px.density_mapbox(
    prices_by_location,
    lat='latitude',
    lon='longitude',
    z='avg_price',
    radius=15,
    center=dict(lat=-27.5954, lon=-48.5480),  # Florianópolis
    zoom=10,
    mapbox_style="open-street-map",
    title="Preço Médio por Bairro"
)
fig.show()
```

### 3. Desertos de Preços Baixos

```sql
-- Bairros sem opção barata (apenas lojas caras)
WITH location_prices AS (
    SELECT
        l.location_id,
        l.neighborhood_name,
        s.store_name,
        AVG(p.min_price) as avg_price,
        RANK() OVER (PARTITION BY l.location_id ORDER BY AVG(p.min_price)) as price_rank
    FROM fct_daily_prices p
    JOIN dim_location l ON p.location_key = l.location_key
    JOIN dim_store s ON p.store_key = s.store_key
    GROUP BY l.location_id, l.neighborhood_name, s.store_name
)
SELECT
    neighborhood_name,
    COUNT(DISTINCT store_name) as stores_in_area,
    MIN(avg_price) as cheapest_store_avg,
    MAX(avg_price) as most_expensive_store_avg
FROM location_prices
GROUP BY neighborhood_name
HAVING MIN(avg_price) > 25.00  -- Nem a loja mais barata tem média < R$25
ORDER BY cheapest_store_avg DESC;
```

### 4. Coverage Gap Analysis

```sql
-- Lojas que NÃO estão presentes em determinada localização
SELECT
    l.neighborhood_name,
    s.store_name,
    CASE WHEN sl.store_location_key IS NULL THEN 'Ausente' ELSE 'Presente' END as status
FROM dim_location l
CROSS JOIN dim_store s
LEFT JOIN dim_store_location sl
    ON l.location_key = sl.location_key
    AND s.store_key = sl.store_key
WHERE l.city_name = 'Florianópolis'
ORDER BY l.neighborhood_name, s.store_name;
```

---

## 🔧 Implementação

### Passo 1: Extrair Localizações Únicas

```python
# scripts/extract_unique_locations.py

import yaml
import pandas as pd
from pathlib import Path

# Ler stores.yaml
with open('config/stores.yaml') as f:
    stores_config = yaml.safe_load(f)

locations = []

for store_id, store_config in stores_config['stores'].items():
    for region_id, region_config in store_config['regions'].items():
        # Parsear city e neighborhood
        parts = region_id.split('_', 1)
        city = parts[0]
        neighborhood = parts[1] if len(parts) > 1 else 'centro'

        locations.append({
            'location_id': region_id,
            'city_code': city,
            'neighborhood_code': neighborhood,
            'cep': region_config['cep'],
            'hub_id': region_config.get('hub_id'),
            'source_store': store_id  # Para debug
        })

# Deduplicate (pode haver múltiplas lojas no mesmo location_id)
locations_df = pd.DataFrame(locations).drop_duplicates('location_id')

# Enriquecer com dados de CEP → lat/long (usar API ViaCEP ou Google)
# ...

print(f"Localizações únicas encontradas: {len(locations_df)}")
locations_df.to_csv('data/bronze/unique_locations.csv', index=False)
```

### Passo 2: Criar Modelo DBT

```sql
-- models/marts/conformed/dim_location.sql

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension', 'location']
    )
}}

with
    locations_from_config as (
        select
            location_id,
            city_code,
            neighborhood_code,
            cep
        from {{ source('bronze', 'unique_locations') }}
    )

    , with_geocoding as (
        select
            location_id,
            -- Map city codes to full names
            case city_code
                when 'florianopolis' then 'Florianópolis'
                when 'tubarao' then 'Tubarão'
                when 'criciuma' then 'Criciúma'
                when 'blumenau' then 'Blumenau'
                -- ... etc
            end as city_name,
            neighborhood_code,
            -- Enriquecer com nomes de bairros
            case neighborhood_code
                when 'costeira' then 'Costeira do Pirajubaé'
                when 'santa_monica' then 'Santa Mônica'
                when 'sacogrande' then 'Saco Grande'
                -- ... etc
            end as neighborhood_name,
            cep,
            -- TODO: Geocoding (lat/long) via API externa
            null::decimal(9,6) as latitude,
            null::decimal(9,6) as longitude
        from locations_from_config
    )

    , with_surrogate_key as (
        select
            row_number() over (order by location_id) as location_key,
            *
        from with_geocoding
    )

select * from with_surrogate_key
```

### Passo 3: Criar Bridge Table

```sql
-- models/marts/conformed/dim_store_location.sql

{{
    config(
        materialized='table',
        tags=['conformed', 'dimension', 'bridge']
    )
}}

with
    store_regions as (
        -- Extrair combinações store + region do bronze
        select distinct
            supermarket as store_id,
            region_code
        from {{ ref('tru_product') }}
    )

    , with_keys as (
        select
            sr.store_id,
            sr.region_code,
            s.store_key,
            l.location_key
        from store_regions sr
        join {{ ref('dim_store') }} s on sr.store_id = s.store_id
        join {{ ref('dim_location') }} l on sr.region_code = l.location_id
    )

    , with_metadata as (
        select
            row_number() over () as store_location_key,
            store_key,
            location_key,
            -- TODO: Adicionar hub_id, store_address de config/stores.yaml
            null as hub_id,
            null as store_address,
            true as is_active
        from with_keys
    )

select * from with_metadata
```

### Passo 4: Atualizar `fct_daily_prices`

```sql
-- Adicionar location_key
ALTER TABLE fct_daily_prices
ADD COLUMN location_key INTEGER;

-- Migrar dados
UPDATE fct_daily_prices dp
SET location_key = sl.location_key
FROM dim_store_location sl
WHERE dp.store_key = sl.store_key;

-- Adicionar FK constraint
ALTER TABLE fct_daily_prices
ADD CONSTRAINT fk_location
FOREIGN KEY (location_key) REFERENCES dim_location(location_key);
```

---

## 📚 Roadmap

### Fase 1: Fundação ✅ (Agora)
- [x] Documentar problema e solução
- [ ] Criar `dim_location`
- [ ] Criar `dim_store_location`
- [ ] Migrar `fct_daily_prices` para usar `location_key`

### Fase 2: Enriquecimento (1-2 semanas)
- [ ] Geocoding (CEP → lat/long) via API ViaCEP
- [ ] Adicionar dados de endereço completo das lojas
- [ ] Popular `neighborhood_name` com nomes oficiais

### Fase 3: Análises Avançadas (2-3 semanas)
- [ ] Dashboard de mapas de calor (Streamlit + Plotly)
- [ ] Análise de coverage gaps
- [ ] Recomendações de expansão geográfica

### Fase 4: Otimização (ongoing)
- [ ] Cache de geocoding (evitar re-consultar APIs)
- [ ] Atualização automática de lat/long
- [ ] Integração com Google Maps API para rotas

---

**Última atualização:** 2026-02-06
**Autor:** Claude Sonnet 4.5
