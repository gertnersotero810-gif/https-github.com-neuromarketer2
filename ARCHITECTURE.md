# ARCHITECTURE.md — НейроМаркетолог v2.0

> **Статус:** Живой документ. Обновляется Архитектором при каждом изменении контракта.  
> **Роль:** Единственный источник истины для всей команды (ролей AI-оркестратора).  
> Ревьюер обязан сверяться с этим файлом после каждой выполненной задачи.

---

## 1. МИССИЯ И ЦЕЛЕВАЯ АУДИТОРИЯ

**Продукт:** «AI-Copilot» — рабочее пространство для performance-маркетологов, CMO и агентств.  
**Роль системы:** «AI-Директор» — удерживает фокус на KPI, помнит контекст бизнеса, бьёт тревогу при отклонениях.  
**MVP-принцип:** Реализуем минимально жизнеспособный продукт. YAGNI ruthlessly.

---

## 2. ПОЛНЫЙ ТЕХНОЛОГИЧЕСКИЙ СТЕК (с версиями)

### Backend
| Компонент | Версия | Назначение |
|---|---|---|
| Python | 3.11+ | Основной язык |
| FastAPI | 0.115.x | Async HTTP-фреймворк |
| SQLAlchemy | 2.0.x (async) | ORM с async engine |
| SQLModel | 0.0.21+ | Pydantic+SQLAlchemy интеграция |
| Alembic | 1.13.x | Версионирование миграций БД |
| Pydantic | 2.x | Валидация данных и JSON Schema |
| httpx | 0.27.x | HTTP-клиент для LLM API (единственный способ) |
| langgraph | **1.1.x** | Оркестрация агентных графов |
| langchain-core | **1.3.x** | Базовые абстракции (messages, tools) |
| asyncpg | 0.29.x | Async PostgreSQL драйвер |
| python-jose | 3.3.x | JWT токены |
| bcrypt | 4.x | Хэширование паролей (прямой, без passlib) |
| pandas | 2.2.x | Выполнение сгенерированных скриптов нормализации |

### Database
| Компонент | Версия | Назначение |
|---|---|---|
| PostgreSQL | 16.x | Основная СУБД |
| Row-Level Security | built-in | Мультитенантная изоляция |
| JSONB + GIN | built-in | Хранение сырых метрик |
| Materialized Views | built-in | Агрегация в витрины данных |

### Frontend
| Компонент | Версия | Назначение |
|---|---|---|
| React | 18.x | UI-фреймворк |
| TypeScript | 5.x | Типизация |
| Vite | 5.x | Сборщик |
| react-grid-layout | 1.4.x | Draggable/resizable сетка виджетов |
| Recharts | 2.x + ResponsiveContainer | SVG-графики с авто-ресайзом |
| TanStack Query | 5.x | Server state management |
| Axios | 1.x | HTTP-клиент |

### Инфраструктура
| Компонент | Версия | Назначение |
|---|---|---|
| Docker + Docker Compose | latest | Оркестрация сервисов |
| nginx | alpine | Reverse proxy (frontend → backend) |

### Боilerplate-основа
Проект стартует на базе **https://github.com/fastapi/full-stack-fastapi-template**  
Из него берём: JWT-аутентификацию, RBAC, async SQLAlchemy setup, Docker Compose скелет, Alembic конфиг.

---

## 3. ЖЁСТКИЕ ЗАПРЕТЫ (нарушение = блокировка Ревьюером)

```
❌ ЗАПРЕЩЕНО                                  ✅ ОБЯЗАТЕЛЬНО
─────────────────────────────────────────     ────────────────────────────────────────
langchain-openai, langchain-community,        langgraph, langchain-core — можно
  любые langchain-* кроме двух выше
Синхронные SQLAlchemy паттерны               Только async session + await
  (session.execute без await)
Прямой импорт openai SDK в бизнес-логике     Только через LLMProvider интерфейс
dbt, любые ETL-фреймворки                    Materialized Views нативный PostgreSQL
Хардкод секретов в коде                      Только через .env + pydantic Settings
Передача тела CSV файла в LLM               Только headers + 3 sample rows
Хардкод аналитических таблиц на фронте      Только widgetArray от бэкенда
SELECT с правами записи в агенте             Read-only соединение для Text-to-SQL
```

### 3.1 ФУНДАМЕНТАЛЬНЫЕ АРХИТЕКТУРНЫЕ ПАТТЕРНЫ

**IMPORT PIPELINE:**
- `file_hash`: SHA-256 файла сохраняется при `/analyze`, проверяется при `/commit` (защита от подмены файла).
- Колонки с coverage < 60% не предлагаются к маппингу.
- Транзакционный upsert: батчинг по 1000 строк, `try/except/rollback` на весь commit.
- `pd.to_datetime(..., errors='coerce')` для защиты от битых дат.

**LLM КОНТЕКСТ:**
- История чата: скользящее окно последних 10 сообщений.
- `build_project_context`: truncate всех текстовых полей до 1000 символов (защита токенов).
- Лимит задач от ИИ в bulk: не более 50 за один запрос.

**FRONTEND:**
- `crypto.randomUUID()` для временных ID черновиков (нативный браузерный API, без сторонних пакетов).
- `AbortController` применять на ЛЮБОЙ `useEffect` с `fetch/axios` (особенно важно для race conditions).

---

## 4. СХЕМА БАЗЫ ДАННЫХ

### 4.1 Таблица `tenants`
```sql
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,  -- для поддомена/маршрутизации
    plan        VARCHAR(50) NOT NULL DEFAULT 'trial',  -- trial|pro|enterprise
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- RLS не применяется к самой таблице tenants (системная таблица)
```

### 4.2 Таблица `users`

> **Дизайн-решение:** Пользователь глобален и может быть участником
> нескольких тенантов (компаний-клиентов). Принадлежность к тенанту
> хранится в `user_tenant_memberships`. RLS к `users` напрямую не применяется.

```sql
CREATE TABLE users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    full_name        VARCHAR(255),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Нет tenant_id: пользователь глобален, принадлежность через memberships
CREATE INDEX idx_users_email ON users(email);
-- RLS НЕ применяется к users напрямую (управляется через memberships)
```

### 4.2b Таблица `user_tenant_memberships`

```sql
CREATE TABLE user_tenant_memberships (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role       VARCHAR(50) NOT NULL DEFAULT 'member', -- owner|admin|member
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, tenant_id)  -- один пользователь = одна роль в тенанте
);
CREATE INDEX idx_memberships_user_id ON user_tenant_memberships(user_id);
CREATE INDEX idx_memberships_tenant_id ON user_tenant_memberships(tenant_id);

-- RLS
ALTER TABLE user_tenant_memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY memberships_tenant_isolation ON user_tenant_memberships
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

**JWT и deps.py:**
- JWT-токен содержит два клейма: `user_id: UUID` и `tenant_id: UUID` (активный тенант в текущей сессии).
- `get_current_user` проверяет, что пара `(user_id, tenant_id)` существует в `user_tenant_memberships`. Если нет — `403 Forbidden`.
- При смене активного тенанта маркетолог получает новый JWT с другим `tenant_id` — без перелогина.

### 4.3 Таблица `projects`
```sql
CREATE TABLE projects (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    niche        VARCHAR(255),              -- контекст бизнеса (глобальная память)
    usp          TEXT,                      -- УТП для AI-Директора
    team_context JSONB DEFAULT '{}',        -- состав команды, роли
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_projects_tenant_id ON projects(tenant_id);

-- RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY projects_tenant_isolation ON projects
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 4.4 Таблица `raw_metrics`
```sql
CREATE TABLE raw_metrics (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    import_batch  UUID NOT NULL,           -- группировка по загрузке файла
    raw_data      JSONB NOT NULL,          -- исходные данные в сыром виде
    normalized    JSONB,                   -- результат Pandas-скрипта нормализации
    -- Извлечённые поля для индексации (из normalized):
    metric_date   DATE,
    campaign_id   VARCHAR(255),
    imported_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Обычные индексы
CREATE INDEX idx_raw_metrics_project_id ON raw_metrics(project_id);
CREATE INDEX idx_raw_metrics_tenant_id ON raw_metrics(tenant_id);
CREATE INDEX idx_raw_metrics_batch ON raw_metrics(import_batch);
CREATE INDEX idx_raw_metrics_date ON raw_metrics(metric_date);

-- Частичные GIN-индексы для JSONB (только ключи участвующие в фильтрации)
CREATE INDEX idx_raw_metrics_campaign_gin
    ON raw_metrics USING GIN ((normalized -> 'campaign_id') jsonb_path_ops)
    WHERE normalized IS NOT NULL;

CREATE INDEX idx_raw_metrics_date_gin
    ON raw_metrics USING GIN ((normalized -> 'date') jsonb_path_ops)
    WHERE normalized IS NOT NULL;

-- RLS
ALTER TABLE raw_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY raw_metrics_tenant_isolation ON raw_metrics
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 4.5 Materialized View `metrics_daily_mv`
```sql
CREATE MATERIALIZED VIEW metrics_daily_mv AS
SELECT
    project_id,
    tenant_id,
    metric_date,
    (normalized->>'campaign_id')::VARCHAR   AS campaign_id,
    SUM((normalized->>'impressions')::BIGINT) AS impressions,
    SUM((normalized->>'clicks')::BIGINT)      AS clicks,
    SUM((normalized->>'spend')::NUMERIC)      AS spend,
    SUM((normalized->>'conversions')::BIGINT) AS conversions,
    CASE
        WHEN SUM((normalized->>'clicks')::BIGINT) > 0
        THEN SUM((normalized->>'clicks')::BIGINT)::FLOAT
             / SUM((normalized->>'impressions')::BIGINT)
        ELSE 0
    END AS ctr,
    CASE
        WHEN SUM((normalized->>'spend')::NUMERIC) > 0
        THEN SUM((normalized->>'conversions')::BIGINT)::NUMERIC
             / SUM((normalized->>'spend')::NUMERIC)
        ELSE 0
    END AS roas
FROM raw_metrics
WHERE normalized IS NOT NULL
GROUP BY project_id, tenant_id, metric_date,
         (normalized->>'campaign_id');

-- Индекс на MV
CREATE UNIQUE INDEX idx_metrics_daily_mv_pk
    ON metrics_daily_mv(project_id, metric_date, campaign_id);
CREATE INDEX idx_metrics_daily_mv_project_date
    ON metrics_daily_mv(project_id, metric_date DESC);

-- Обновление: REFRESH MATERIALIZED VIEW CONCURRENTLY metrics_daily_mv;
-- Запускается через scheduled job (APScheduler) каждый час.
```

### 4.6 Таблица `dashboard_layouts`
```sql
CREATE TABLE dashboard_layouts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    layout_data JSONB NOT NULL,   -- widgetArray: полный массив виджетов с координатами
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, user_id)   -- один layout на пользователя на проект
);

-- Индексы
CREATE INDEX idx_dashboard_layouts_project_user
    ON dashboard_layouts(project_id, user_id);

-- RLS
ALTER TABLE dashboard_layouts ENABLE ROW LEVEL SECURITY;
CREATE POLICY dashboard_layouts_tenant_isolation ON dashboard_layouts
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 4.7 Таблица `usage_logs`
```sql
CREATE TABLE usage_logs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE SET NULL,
    model             VARCHAR(100) NOT NULL,       -- 'gpt-4o-mini'
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    cost_usd          NUMERIC(10, 6) NOT NULL DEFAULT 0,
    operation         VARCHAR(100) NOT NULL,       -- 'csv_mapping' | 'anomaly_verify' | 'text_to_sql'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_logs_tenant_id ON usage_logs(tenant_id);
CREATE INDEX idx_usage_logs_created_at ON usage_logs(created_at DESC);
-- RLS
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY usage_logs_tenant_isolation ON usage_logs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

---

## 5. LLMProvider — АБСТРАКЦИЯ И ПРАВИЛО

### 5.1 Интерфейс (единственная точка входа)

```python
# backend/app/core/llm_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class UsageInfo:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float  # рассчитывается провайдером исходя из model pricing

@dataclass  
class LLMResponse:
    content: str
    usage: UsageInfo

class LLMProvider(ABC):
    """
    Единственная точка входа для всех LLM-вызовов.
    Бизнес-логика НИКОГДА не импортирует конкретный SDK напрямую.
    """
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:  # ← возвращает LLMResponse, а не str
        ...
```

### 5.2 Конкретная реализация

```python
# backend/app/core/llm_providers/openai_provider.py
import httpx
from backend.app.core.llm_provider import LLMProvider, LLMResponse, UsageInfo

class OpenAIProvider(LLMProvider):
    """
    Реализует LLMProvider через прямые httpx-запросы к OpenAI API.
    Никаких langchain-openai, никакого openai SDK в бизнес-коде.
    base_url — параметр: позволяет переключить на любой OpenAI-совместимый API
    (Ollama, vLLM, LM Studio) одной строкой в .env.
    """
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url  # https://api.openai.com/v1 или http://localhost:11434/v1

    async def complete(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            usage_data = data.get("usage", {})
            
            # Прайсинг gpt-4o-mini (актуален на момент написания, вынести в config):
            COST_PER_1K_INPUT  = 0.000150   # $0.150 per 1M input tokens
            COST_PER_1K_OUTPUT = 0.000600   # $0.600 per 1M output tokens
            cost = (
                usage_data.get("prompt_tokens", 0) * COST_PER_1K_INPUT / 1000 +
                usage_data.get("completion_tokens", 0) * COST_PER_1K_OUTPUT / 1000
            )
            
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                    cost_usd=cost,
                )
            )
```

### 5.3 Правило изоляции

```
ПРАВИЛО: Ни один файл в backend/services/, backend/api/, backend/agents/
         НЕ ИМЕЕТ ПРАВА импортировать:
           - openai
           - langchain-openai
           - anthropic
           - любой другой LLM SDK напрямую

         Допустимо ТОЛЬКО:
           from backend.core.llm_provider import LLMProvider
         
         Внедрение через Dependency Injection FastAPI:
           async def route(llm: LLMProvider = Depends(get_llm_provider)):
```

---

## 6. КОНТРАКТ widgetArray (Server-Driven UI)

### 6.1 JSON Schema объекта виджета

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Widget",
  "type": "object",
  "required": ["i", "x", "y", "w", "h", "chart", "dataKey", "title"],
  "properties": {
    "i": {
      "type": "string",
      "description": "Уникальный идентификатор виджета (UUID). Используется react-grid-layout как ключ ячейки.",
      "example": "widget-ctr-daily-01"
    },
    "x": {
      "type": "integer",
      "minimum": 0,
      "maximum": 11,
      "description": "Позиция по горизонтали в сетке (0–11, 12-колоночная сетка)"
    },
    "y": {
      "type": "integer",
      "minimum": 0,
      "description": "Позиция по вертикали (единица = 1 row unit react-grid-layout)"
    },
    "w": {
      "type": "integer",
      "minimum": 1,
      "maximum": 12,
      "description": "Ширина в колонках"
    },
    "h": {
      "type": "integer",
      "minimum": 1,
      "description": "Высота в row units"
    },
    "chart": {
      "type": "string",
      "enum": ["line", "bar", "pie", "area", "number"],
      "description": "Тип визуализации. 'number' — единственное число (KPI-карточка)."
    },
    "dataKey": {
      "type": "string",
      "description": "Поле из metrics_daily_mv для оси Y (ctr, roas, spend, clicks, impressions, conversions)",
      "example": "ctr"
    },
    "title": {
      "type": "string",
      "description": "Заголовок виджета, отображаемый пользователю",
      "example": "CTR по дням"
    },
    "filters": {
      "type": "object",
      "description": "Опциональные фильтры запроса данных",
      "properties": {
        "campaign_id": { "type": "string" },
        "date_from": { "type": "string", "format": "date" },
        "date_to": { "type": "string", "format": "date" }
      }
    }
  }
}
```

### 6.2 Пример widgetArray ответа

```json
{
  "widgets": [
    {
      "i": "widget-ctr-01",
      "x": 0, "y": 0, "w": 6, "h": 4,
      "chart": "line",
      "dataKey": "ctr",
      "title": "CTR по дням",
      "filters": { "date_from": "2024-01-01", "date_to": "2024-01-31" }
    },
    {
      "i": "widget-spend-02",
      "x": 6, "y": 0, "w": 6, "h": 4,
      "chart": "bar",
      "dataKey": "spend",
      "title": "Расходы по кампаниям"
    },
    {
      "i": "widget-roas-kpi-03",
      "x": 0, "y": 4, "w": 3, "h": 2,
      "chart": "number",
      "dataKey": "roas",
      "title": "ROAS (общий)"
    }
  ]
}
```

### 6.3 API-контракт

```
GET  /api/v1/projects/{project_id}/dashboard
     → { widgets: Widget[] }
     
PUT  /api/v1/projects/{project_id}/dashboard/layout
     Body: { widgets: Widget[] }   ← сохраняет персональную сетку пользователя
     → { status: "saved", updated_at: "ISO8601" }
```

### 6.4 Архитектура и Отрисовка Дашборда на Фронтенде

Фронтенд-слой спроектирован полностью по принципу Server-Driven UI, где состав, заголовки, типы графиков и координаты ячеек задаются массивом `widgetArray` с бэкенда, сохраняя абсолютную независимость логики от захардкоженных структур.

#### 6.4.1 Адаптивная сетка (Responsive Grid)
* **Библиотека:** `react-grid-layout` (компонент `ResponsiveReactGridLayout` с оберткой `WidthProvider`).
* **Точки останова (Breakpoints):** Сконфигурированы для основных размеров экранов (`lg: 1200`, `md: 996`, `sm: 768` и др.) с динамическим распределением колонок (12, 10, 6 соответственно).
* **Синхронизация и защита от спама (Layout Persistence & Anti-Spam):**
  * Перемещение и масштабирование виджетов обновляют только локальный реактивный стейт `localWidgets` через обработчик `onLayoutChange`, что гарантирует плавность отрисовки (60fps) во время перетаскивания.
  * Фактическая отправка `PUT` запроса сохранения макета на бэкенд вынесена из горячего цикла и выполняется строго по завершении действий — на дискретных событиях `onDragStop` и `onResizeStop`.
* **Сетевой жизненный цикл (Network Query Cancellation):**
  * Получение данных дашборда (`useGetDashboard`) использует встроенную отмену запросов React Query. Контекстный `signal` из `queryFn` автоматически пробрасывается в Axios-конфигурацию, прекращая фоновые запросы при переключении страниц или размонтировании дашборда.

#### 6.4.2 Слой рендеринга виджетов (Widget Renderer Architecture)
* **Компонент:** `WidgetRenderer` принимает объект `Widget` и выполняет динамический выбор отображения через `switch(chart)`:
  * `line` → `LineChart` (Recharts) с плавным сглаживанием линий.
  * `bar` → `BarChart` (Recharts) с закругленными гранями столбцов (`radius`).
  * `area` → `AreaChart` (Recharts) с полупрозрачным фоновым индиго-градиентом.
  * `pie` → `PieChart` (Recharts) кольцевой структуры с палитрой неоновых цветов.
  * `number` → KPI-карточка с выводом последней точки данных крупным кеглем (`2.75rem`) и индикатором роста/динамики.
* **Карточный Empty State (Card-Level Empty State):**
  * В соответствии с Server-Driven UI контрактом, в приложении полностью ликвидированы захардкоженные демонстрационные массивы данных на фронтенде.
  * Если `widget.data` отсутствует или пуст (например, при пустом материализованном представлении `metrics_daily_mv`), внутри тела карточки рендерится аккуратный пустой экран («Нет данных для отображения») с предложением импортировать CSV-файлы отчетов. Заголовок и тип виджета на панели при этом сохраняются.
* **Масштабирование:** Каждый график Recharts изолирован в элементе `<ResponsiveContainer width="100%" height="100%">` для мгновенной адаптации SVG к изменениям размеров ячеек сетки.

#### 6.4.3 Визуальный слой и тема (Premium Dark UI Layer)
* **Дизайн-система:** Глубокая темная аналитическая тема (цветовая палитра: фон `#0a0a0f` с верхним радиальным градиентом свечения, поверхность виджетов `#11111a`, границы `rgba(255, 255, 255, 0.08)`).
* **Кастомизация Recharts:**
  * Сетки графиков (`CartesianGrid`) используют мягкий цвет `rgba(255, 255, 255, 0.04)`.
  * Оси `XAxis`/`YAxis` и линии скрыты, отображаются только контрастные подписи.
  * Тултипы (`Tooltip`) стилизованы в виде темных плашек с размытием заднего плана (`backdrop-filter: blur(8px)`).
* **Стратегия скелетонов загрузки (Loading Skeleton Strategy):** В процессе загрузки вместо стандартных спиннеров рендерится полноценный макет сетки, имитирующий очертания виджетов, с мягким CSS-эффектом затухания и пульсации (`animate-pulse`).

---

## 7. СХЕМА LANGGRAPH — AI-Директор

### 7.1 AnomalyState (TypedDict)

```python
# backend/agents/anomaly_state.py
from typing import TypedDict, Optional
from datetime import date

class AnomalyCandidate(TypedDict):
    metric: str           # 'ctr' | 'roas' | 'spend'
    campaign_id: str
    metric_date: str      # ISO date
    value: float
    z_score: float        # отклонение в σ
    direction: str        # 'spike' | 'drop'

class AnomalyState(TypedDict):
    project_id: str
    tenant_id: str
    analysis_date: str                          # дата анализа
    metrics_snapshot: list[dict]                # сырые данные из metrics_daily_mv
    candidates: list[AnomalyCandidate]          # кандидаты от Detection Node
    verified_anomalies: list[AnomalyCandidate]  # подтверждённые Verification Node
    pending_approval: bool                      # True = граф остановлен (HITL)
    approval_payload: Optional[dict]            # payload изменения (бюджет / статус)
    error: Optional[str]                        # ошибка на любом узле
```

### 7.2 Граф и переходы

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                    AnomalyDetectionGraph                        │
 │                                                                 │
 │  START ──► [Detection Node] ──► [Verification Node]             │
 │                                        │                        │
 │                          candidates?   │                        │
 │                         ┌─────────────┤                        │
 │                    YES  ▼        NO   ▼                        │
 │            [HITL Gate Node]     [END: no_anomalies]            │
 │                   │                                             │
 │      budget_change > 20%        │                              │
 │      or fraud detected?         │                              │
 │             │                   │ safe action                  │
 │        YES  ▼              NO   ▼                              │
 │      [INTERRUPT]          [Action Node]                         │
 │   pending_approval=True   (execute safe recommendation)        │
 │   ждёт PUT /approve                                             │
 └─────────────────────────────────────────────────────────────────┘
```

### 7.3 Узлы

| Узел | Входные данные | Выходные данные | Запрещено |
|---|---|---|---|
| **Detection Node** | `metrics_snapshot` из MV | `candidates` (z-score > 2.5σ) | LLM-вызовы |
| **Verification Node** | `candidates` | `verified_anomalies` | SQL-запросы |
| **HITL Gate Node** | `verified_anomalies` | `pending_approval=True/False` | Изменения БД |
| **Action Node** | `verified_anomalies` | рекомендации | Любые DML-запросы |

**Text-to-SQL правило:** Агент использует read-only соединение с БД. Инструмент принимает только `SELECT`-запросы; любой другой тип → исключение `ReadOnlySQLError`.

---

## 8. ПРАВИЛО ZERO-TOUCH ИМПОРТА

```
ЗАПРЕЩЕНО передавать в LLM:
  ❌ Содержимое строк CSV (кроме 3 примеров)
  ❌ Личные данные пользователей
  ❌ Значения метрик (числа в строках данных)

ОБЯЗАТЕЛЬНО передавать:
  ✅ Список заголовков columns: list[str]
  ✅ Ровно 3 строки-примера (sample_rows: list[dict])
  ✅ Целевую схему (target_schema: dict) — Pydantic JSON Schema

ОЖИДАЕМЫЙ ОТВЕТ LLM:
  Валидный Python-скрипт на Pandas.
  Скрипт принимает df: pd.DataFrame и возвращает df_normalized: pd.DataFrame.
  Нормализованные колонки: date, campaign_id, impressions, clicks, spend, conversions.
  response_format={"type": "json_object"} — принудительный JSON Mode.
```

SANDBOX СТРАТЕГИЯ для выполнения Pandas-скрипта:
MVP (MacBook): exec() с жёстко ограниченным globals:
```python
ALLOWED_GLOBALS = {
    "builtins": {
        "len": len, "range": range, "str": str, "int": int,
        "float": float, "list": list, "dict": dict,
        "isinstance": isinstance, "enumerate": enumerate,
    },
    "pd": pandas,
    "datetime": datetime,
}
```
ЗАПРЕЩЕНО в globals: os, sys, subprocess, open, import, eval, exec

ВАЛИДАЦИЯ скрипта ДО exec():
- AST-парсинг: если в дереве есть Import, ImportFrom, Call с именем 'eval'/'exec'/'open'/'import' → ScriptSecurityError, не выполняем
- Скрипт не должен содержать сетевые вызовы

ОБЯЗАТЕЛЬНО: AST-валидация выполняется первой, exec() — второй.

---

## 8b. СЛУЖБА ЭКСПОРТА (ExportService)

### 8b.1 Системный поток (Export Flow)
```
dashboard widgets → ExportService → openpyxl workbook → StreamingResponse
```

### 8b.2 Технические особенности реализации
* **Полностью in-memory:** Экспорт выполняется без создания временных файлов на диске через поток `io.BytesIO`.
* **Async-совместимость:** Код сервиса полностью совместим с асинхронными вызовами FastAPI эндпоинта.
* **XLSX генерация:** Сборка таблиц и стилизация (шрифты, закругления, границы, авто-подгонка ширины колонок) выполняется через `openpyxl`.

### 8b.3 Интеграция с LLM (LLM Usage Contract)
* **Передача только метаданных:** Сырые наборы числовых данных и метрик НИКОГДА не отправляются в LLM.
* **Контракт запроса:** В LLM уходит только `widgets_metadata` (заголовки, типы визуализации, dataKey).
* **Контракт ответа:** LLM рекомендует структуру отчета в формате JSON: названия листов (`sheet_order`) и визуальные секции (`section_names`).
* **Отказоустойчивость:** При сбое, задержке или ошибке LLM-провайдера система бесшовно выполняет graceful fallback: генерирует отчет со структурой по умолчанию ("Dashboard Summary", секции по названию виджетов), без прерывания экспорта.

### 8b.4 Ограничения безопасности (Safety Guards)
* **MAX_WIDGETS = 50:** Максимальное количество обрабатываемых виджетов на один экспорт.
* **MAX_ROWS_PER_WIDGET = 5000:** Лимит строк данных на один виджет.
* **MAX_TOTAL_CELLS = 100_000:** Лимит ячеек данных на весь workbook. При достижении лимита выполняется немедленное прерывание (`hard stop`) дальнейшего прохода по виджетам во избежание OOM.

### 8b.5 Контракт эндпоинта (Endpoint Contract)
* **Маршрут:** `GET /api/v1/projects/{project_id}/dashboard/export`
* **Доступ:** Строгая проверка прав доступа (Tenant Isolation RLS).
* **Тип ответа:** `StreamingResponse` (media_type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

## 9. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://neuro:secret@postgres:5432/neuromarketer
POSTGRES_USER=neuro
POSTGRES_PASSWORD=secret
POSTGRES_DB=neuromarketer

# Auth
SECRET_KEY=<generate: openssl rand -hex 32>
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM Provider
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
# Для переключения на Ollama: OPENAI_BASE_URL=http://ollama:11434/v1

# App
FIRST_SUPERUSER=admin@neuromarketer.io
FIRST_SUPERUSER_PASSWORD=changeme
ENVIRONMENT=development
```

---

## 10. СТРУКТУРА ДИРЕКТОРИЙ (целевая)

```
2neuromarketer-app/
├── backend/
│   ├── alembic/                  # Миграции
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/    # routes: auth, projects, metrics, dashboard, agents
│   │   │       └── deps.py       # FastAPI Depends: get_db, get_current_user, get_llm_provider
│   │   ├── core/
│   │   │   ├── config.py         # pydantic Settings
│   │   │   ├── llm_provider.py   # ABC LLMProvider
│   │   │   └── llm_providers/
│   │   │       └── openai_provider.py
│   │   ├── agents/
│   │   │   ├── anomaly_state.py
│   │   │   └── anomaly_graph.py  # LangGraph граф
│   │   ├── models/               # SQLModel таблицы
│   │   ├── schemas/              # Pydantic схемы (request/response)
│   │   └── services/
│   │       ├── import_service.py # Zero-Touch импорт
│   │       ├── export_service.py # .xlsx in-memory (openpyxl + LLM optional)
│   │       └── dashboard_service.py
│   ├── tests/
│   │   ├── test_rls.py
│   │   ├── test_import.py
│   │   ├── test_agents.py
│   │   └── test_dashboard.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── Dashboard/
│   │   │       ├── DashboardGrid.tsx   # ResponsiveReactGridLayout
│   │   │       └── WidgetRenderer.tsx  # chart-type → Recharts компонент
│   │   └── api/
│   │       └── dashboard.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── ARCHITECTURE.md               ← этот файл
└── IMPLEMENTATION_PLAN.md        ← план реализации
```

---

## 12. ТРЕКЕР ПРОГРЕССА

> Обновляется Ревьюером после каждой задачи. Commit-хэш берётся из `git log --oneline`.

| Задача | Название | Статус | Ревьюер ✓ | Commit |
|--------|----------|--------|-----------|--------|
| 1.1 | Docker + Nginx + Health Check | ✅ | ✅ | `4e5b57e` |
| 1.2 | Alembic + Схема БД + Модели | ✅ | ✅ | `91c9346` |
| 1.3 | RLS + JWT + Auth endpoints | ✅ | ✅ | `ad6f595` |
| 1.4 | LLMProvider + UsageLog | ✅ | ✅ | `0ec786e` |
| 2.1 | CSV upload endpoint | ✅ | ✅ | `a9b6c1b` |
| 2.2 | Schema mapping (LLM + AST) | ✅ | ✅ | `30c77b7` |
| 2.3 | JSONB storage + Mat. View | ✅ | ✅ | `30c77b7` |
| 3.1 | Detection Node (SQL) | ✅ | ✅ | `fc55b10` |
| 3.2 | Verification Node + HITL | ✅ | ✅ | `72c94f1` |
| 3.3 | Text-to-SQL (read-only) | ✅ | ✅ | `2d4acc5` |
| 4.1 | Dashboard API (widgetArray) | ✅ | ✅ | `9aee09b` |
| 4.2 | React Dashboard (grid) | ✅ | ✅ | `c17019f` |
| 4.3 | ExportService (.xlsx) | ✅ | ✅ | `5ca7a10` |

**Правило обновления (ОБЯЗАТЕЛЬНО для Ревьюера):**
После каждой задачи Ревьюер обязан:
1. Изменить ⬜ → ✅ в колонке "Статус"
2. Изменить ⬜ → ✅ в колонке "Ревьюер ✓"
3. Вставить хэш коммита (7 символов) из `git log --oneline -1`
4. Показать grep-подтверждение (см. правило верификации выше)

---

## 11. KNOWN RISKS (Pre-Flight Check — 07.05.2026)

| Риск | Вероятность | Митигация | Затронутые задачи |
|------|-------------|-----------|-------------------|
| **LangGraph/langchain-core 0.2.x/0.3.x — устаревшие, на maintenance mode.** Текущие stable: langgraph **1.1.x**, langchain-core **1.3.x**. Старые версии получают только security patches. | Высокая | Пинить в requirements.txt: `langgraph==1.1.*` + `langchain-core==1.3.*`. Версии в стеке обновлены. | 3.1, 3.2, 3.3 |
| **SQLModel 0.0.21 + SQLAlchemy 2.0 async: нет native async wrappers.** `SQLModel.metadata.create_all` — синхронный, нельзя вызывать напрямую в async-контексте. | Средняя | В Alembic-миграциях использовать `connection.run_sync(SQLModel.metadata.create_all)`. В тестах — аналогично. | 1.2 |
| **RLS: SET LOCAL работает только внутри транзакции.** Без `session.begin()` SET LOCAL не влияет на последующие запросы в той же сессии. | Высокая | `deps.py` обязан использовать `async with session.begin():` и выполнять SET LOCAL первой операцией внутри неё. Тест 1.3 явно проверяет изоляцию. | 1.3 |
| **LLMResponse вместо str — ломает места, ждущие str.** Verification Node и import_service написаны после задачи 1.4 — если не использовать `response.content`, будет TypeError. | Средняя | В задачах 2.2 и 3.2 все места вызова `llm.complete()` используют `response.content`. Чеклист Ревьюера включает эту проверку. | 2.2, 3.2 |
| **postgres:16 Docker** — multi-arch образ, native arm64 доступен для Apple Silicon. Флаг `platform: linux/amd64` не нужен и замедлит контейнер через Rosetta. | Низкая | Не указывать `platform` в docker-compose — Docker выберет native arm64 автоматически. Нет CUDA/nvidia runtime в плане. | 1.1 |
| **asyncpg 0.29.x + SQLAlchemy 2.0**: known conflicts отсутствуют, но необходим `expire_on_commit=False` в `async_sessionmaker` иначе lazy-loading падает после commit. | Низкая | Добавить `expire_on_commit=False` в `async_sessionmaker` при настройке в `config.py`. | 1.1, 1.2 |
| **REFRESH MATERIALIZED VIEW CONCURRENTLY** без UNIQUE-индекса выбрасывает ошибку `cannot refresh concurrently`. | Средняя | UNIQUE-индекс `idx_metrics_daily_mv_pk` создаётся в миграции 003 ДО первого REFRESH. Тест явно проверяет порядок. | 2.3 |
| **Масштабируемость REFRESH MV при 50+ тенантах.** REFRESH CONCURRENTLY создаёт очередь — все тенанты ждут единого job-а. | Средняя | MVP: часовой APScheduler job достаточен. Пост-MVP: партиционирование `raw_metrics` по `tenant_id` + per-tenant refresh расписание. | 2.3, Фаза 5 |

