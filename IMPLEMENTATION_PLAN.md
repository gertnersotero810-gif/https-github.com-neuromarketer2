# НейроМаркетолог v2.0 — Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Построить B2B SaaS-платформу AI-Copilot для performance-маркетологов по 4 фазам.  
**Architecture:** Async FastAPI + PostgreSQL 16 (RLS + JSONB) + LangGraph + Server-Driven UI.  
**Tech Stack:** Python 3.11, FastAPI 0.115, SQLAlchemy 2.0 async, langgraph, httpx, React 18, react-grid-layout, Recharts.

---

## ТРЕКЕР ПРОГРЕССА

| Задача | Название | Статус | Commit |
|--------|----------|--------|--------|
| 1.1 | Docker + Nginx + Health Check | ✅ | `4e5b57e` |
| 1.2 | Alembic + Схема БД + Модели | ✅ | `91c9346` |
| 1.3 | RLS + JWT + Auth endpoints | ✅ | `ad6f595` |
| 1.4 | LLMProvider + UsageLog | ✅ | `0ec786e` |
| 2.1 | CSV upload endpoint | ⬜ | — |
| 2.2 | Schema mapping (LLM + AST) | ⬜ | — |
| 2.3 | JSONB storage + Mat. View | ⬜ | — |
| 3.1 | Detection Node (SQL) | ⬜ | — |
| 3.2 | Verification Node + HITL | ⬜ | — |
| 3.3 | Text-to-SQL (read-only) | ⬜ | — |
| 4.1 | Dashboard API (widgetArray) | ⬜ | — |
| 4.2 | React Dashboard (grid) | ⬜ | — |

---

## ПРОТОКОЛ КОМАНДЫ (читать перед каждой задачей)

### Роли и правила переключения

**🏛 Архитектор** — активен при создании плана и при изменении контракта.  
Проверяет: не нарушают ли задачи принципы ARCHITECTURE.md.

**💻 Кодер** — реализует задачу.  
Правило: **код пишется только после того, как тест написан и запущен (пусть падает).**

**🧪 Тестер** — запускает тесты, фиксирует вывод дословно. Не интерпретирует — только факты.

**🔍 Ревьюер** — активируется после каждой зелёной задачи. Проверяет чеклист:
```
□ Нет запрещённых импортов (langchain-openai, openai SDK напрямую, sync SQLAlchemy)?
□ DoD выполнен полностью (все пункты, не частично)?
□ Контракт с другими компонентами соблюдён?
□ Нет TODO-заглушек в prod-коде?
□ Все секреты только через .env + Settings?
□ Все новые таблицы имеют RLS-политику?
```
Если хотя бы один пункт — NO: **возврат к Кодеру с конкретным замечанием. Блок до исправления.**

**🕵️ Следователь** — активируется в двух случаях:

- **Случай A:** тест падает 3 раза подряд с разными ошибками.  
  → Стоп. Анализ логов. Отчёт пользователю:  
  `Что пробовали / Почему не работает (гипотеза) / Предлагаемое изменение в плане`  
  → Ждёт решения пользователя.

- **Случай B:** Ревьюер фиксирует одну и ту же проблему в 2+ итерациях.  
  → Эскалация: анализ — ошибка в IMPLEMENTATION_PLAN.md или ARCHITECTURE.md?  
  → Предлагает конкретную правку документа.

### Правила прогресса
```
❌ Нельзя начать следующую задачу, пока Ревьюер не поставил ✓ на текущей
❌ Нельзя писать реализацию, пока тест не написан и не запущен (пусть падает)
❌ Git commit только после ✓ от Ревьюера
✅ Каждый commit — атомарный (одна задача = один commit)
```

---

## ФАЗА 1: Инфраструктура и изоляция данных

### Задача 1.1: Docker Compose + базовая структура проекта

**Предусловие:** Пустой репозиторий, Docker установлен.

**Реализация:**
- Создать: `docker-compose.yml`
- Создать: `.env.example`
- Создать: `backend/Dockerfile`
- Создать: `frontend/Dockerfile`
- Создать: `backend/app/core/config.py` (pydantic Settings)
- Создать: `backend/app/main.py` (FastAPI app)

**Тест:**
```
Файл: backend/tests/test_infra.py
Проверяет: приложение стартует и /api/v1/health возвращает 200
Команда: docker compose up -d && pytest backend/tests/test_infra.py -v
Ожидаемый вывод: PASSED test_health_check
```

**DoD:**
- `docker compose up` поднимает postgres, backend, frontend без ошибок
- `GET /api/v1/health` → `{"status": "ok"}` с кодом 200
- `.env.example` содержит все переменные из ARCHITECTURE.md секция 9
- `config.py` читает все переменные через `pydantic_settings.BaseSettings`

**Контракт:** Предоставляет рабочее окружение для задач 1.2–1.3.

---

### Задача 1.2: Alembic + схема БД + модели SQLModel

**Предусловие:** Задача 1.1 ✓

**Реализация:**
- Создать: `backend/alembic/` (init)
- Создать: `backend/app/models/tenant.py`
- Создать: `backend/app/models/user.py`
- Создать: `backend/app/models/project.py`
- Создать: `backend/app/models/raw_metric.py`
- Создать: `backend/app/models/dashboard_layout.py`
- Создать: `backend/app/models/usage_log.py` — таблица `usage_logs` (tenant_id, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, created_at)
- Создать: `backend/alembic/versions/001_initial_schema.py`

**Тест:**
```
Файл: backend/tests/test_migrations.py
Проверяет: миграции применяются без ошибок, все таблицы существуют
Команда: pytest backend/tests/test_migrations.py::test_all_tables_exist -v
Ожидаемый вывод: PASSED — все таблицы (tenants, users, projects, raw_metrics, dashboard_layouts) в pg_tables
```

**DoD:**
- `alembic upgrade head` выполняется без ошибок на чистой БД
- `alembic downgrade base` откатывает без ошибок
- Все 6 таблиц созданы с правильными типами (UUID primary keys, TIMESTAMPTZ, JSONB), включая `usage_logs`
- Все GIN-индексы из ARCHITECTURE.md секция 4.4 присутствуют

**Контракт:** Предоставляет схему БД для задач 1.3 и всех последующих фаз.

---

### Задача 1.3: Row-Level Security (RLS) + JWT-аутентификация

**Предусловие:** Задача 1.2 ✓

**Реализация:**
- Создать: `backend/alembic/versions/002_rls_policies.py` (RLS-политики для users, projects, raw_metrics, dashboard_layouts)
- Создать: `backend/app/core/security.py` (JWT encode/decode, password hashing)
- Создать: `backend/app/api/v1/endpoints/auth.py` (POST /login, POST /register)
- Создать: `backend/app/api/v1/deps.py` (get_db с установкой `app.current_tenant_id`)

**Тест:**
```
Файл: backend/tests/test_rls.py
Проверяет: tenant_A не видит данные tenant_B на уровне БД
Команда: pytest backend/tests/test_rls.py::test_tenant_isolation -v
Ожидаемый вывод: PASSED
Ключевой assert:
  # Создаём project для tenant_A и tenant_B
  # Устанавливаем app.current_tenant_id = tenant_A.id
  # SELECT * FROM projects → должен вернуть только проекты tenant_A
  assert all(p.tenant_id == tenant_a.id for p in result)
  assert len([p for p in result if p.tenant_id == tenant_b.id]) == 0
```

**DoD:**
- `SELECT * FROM projects` под tenant_A возвращает 0 строк принадлежащих tenant_B
- То же верно для таблиц users, raw_metrics, dashboard_layouts
- `POST /auth/login` с корректными данными → JWT access_token
- `POST /auth/login` с неверным паролем → 401
- deps.py устанавливает `SET LOCAL app.current_tenant_id` в каждой транзакции

**Контракт:** Предоставляет `get_current_user` и `get_db` для всех защищённых эндпоинтов.

---

### Задача 1.4: LLMProvider абстракция + OpenAIProvider

**Предусловие:** Задача 1.1 ✓ (нужен только config.py)

**Реализация:**
- Изменить: `backend/app/core/llm_provider.py` — возвращает `LLMResponse`
- Создать: `backend/app/core/llm_providers/openai_provider.py` (httpx реализация)
- Создать: `backend/app/models/usage_log.py` — SQLModel модель
- Добавить: `backend/alembic/versions/001_initial_schema.py` — таблица `usage_logs`
- Изменить: `backend/app/api/v1/deps.py` — добавить `get_llm_provider()` и сервис логирования как Depends

**Тест:**
```
Файл: backend/tests/test_llm_provider.py::test_usage_logged_on_complete
Проверяет: каждый LLM-вызов записывает строку в usage_logs
Команда: pytest backend/tests/test_llm_provider.py::test_usage_logged_on_complete -v
Ожидаемый assert:
  # Мокаем httpx → возвращаем ответ с usage: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
  response = await provider.complete([{"role": "user", "content": "ping"}], tenant_id="test-tenant", operation="csv_mapping")
  assert isinstance(response, LLMResponse)
  assert response.usage.total_tokens == 30
  # Проверяем запись в БД
  logs = await db.execute(select(UsageLog).where(UsageLog.tenant_id == tenant_id))
  assert len(logs.all()) == 1
  assert logs[0].operation == 'csv_mapping'
```

**DoD:**
- `OpenAIProvider.complete()` работает через `httpx.AsyncClient` (подтверждено моком)
- `base_url` — параметр конструктора (не хардкод)
- Ни один файл в `app/services/`, `app/api/`, `app/agents/` не импортирует openai SDK напрямую
- `get_llm_provider()` в deps.py инстанциирует `OpenAIProvider` из Settings
- **Каждый вызов `LLMProvider.complete()` создаёт запись в `usage_logs`** с полями: `tenant_id`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `created_at`
- **`cost_usd` заполняется корректно** по актуальному прайсингу gpt-4o-mini: `input $0.150 / 1M tokens`, `output $0.600 / 1M tokens` — формула: `(prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)`
- **Все вызывающие места** (`import_service`, агентные узлы) передают `tenant_id` в `LLMProvider.complete()` — сигнатура расширена: `complete(..., tenant_id: str) -> str`
- Тест: после мока вызова `complete()` в `usage_logs` появляется ровно 1 запись с ненулевым `cost_usd`

**Контракт:** Предоставляет `LLMProvider` интерфейс + `usage_logs` для Фаз 2, 3 и будущей Фазы 5.

---

### Чекпоинт Фазы 1

```
git tag phase-1-complete
```

**Критерий:** Все тесты 1.1–1.4 зелёные. Ревьюер проверил чеклист по всем 4 задачам.

---

## ФАЗА 2: Zero-Touch импорт и хранилище

### Задача 2.1: Async CSV upload endpoint

**Предусловие:** Фаза 1 ✓

**Реализация:**
- Создать: `backend/app/api/v1/endpoints/metrics.py`
  - `POST /api/v1/projects/{project_id}/import` — принимает `UploadFile`
- Создать: `backend/app/services/import_service.py`
  - `extract_headers_and_samples(file: UploadFile) -> tuple[list[str], list[dict]]`

**Тест:**
```
Файл: backend/tests/test_import.py::test_endpoint_extracts_only_headers
Проверяет: эндпоинт читает только заголовки + 3 строки, не передаёт тело в LLM
Команда: pytest backend/tests/test_import.py::test_endpoint_extracts_only_headers -v
Ожидаемый assert:
  # Загружаем CSV с 1000 строками
  # Мокаем llm_provider.complete → записываем переданные messages
  # Проверяем что в messages нет строк 4..1000
  assert len(captured_messages[0]["content"]) < 2000  # не весь CSV
  assert "headers" in captured_messages[0]["content"]
```

**DoD:**
- LLM получает: только `columns: list[str]` + `sample_rows: list[dict]` (ровно 3)
- LLM не получает: строки с 4-й по последнюю
- Endpoint возвращает `{"import_batch": UUID, "status": "processing"}`
- Файл > 50MB → 413 с читаемым сообщением

**Контракт:** Предоставляет `import_batch` UUID для задачи 2.2.

---

### Задача 2.2: LLM Schema Mapping + генерация Pandas-скрипта

**Предусловие:** Задача 2.1 ✓

**Реализация:**
- Изменить: `backend/app/services/import_service.py`
  - `generate_normalization_script(headers, samples, llm: LLMProvider) -> str`
  - `execute_normalization_script(script: str, df: pd.DataFrame) -> pd.DataFrame`
- Создать: `backend/app/schemas/import_schema.py` (Pydantic target schema → JSON Schema для LLM)

**Тест:**
```
Файл: backend/tests/test_import.py::test_schema_mapping_arbitrary_columns
Проверяет: произвольные заголовки → нормализованная схема
Команда: pytest backend/tests/test_import.py::test_schema_mapping_arbitrary_columns -v
Ожидаемый assert:
  # CSV с заголовками: "Дата", "Название кампании", "Показы", "Клики", "Бюджет"
  result_df = await import_service.process(headers, samples, mock_llm)
  assert set(result_df.columns) >= {"date", "campaign_id", "impressions", "clicks", "spend"}
  assert pd.api.types.is_datetime64_any_dtype(result_df["date"])
```

**DoD:**
- **Шаг 1 (ДО exec):** AST-валидация скрипта через `ast.parse()`:
  - `ast.Import` / `ast.ImportFrom` в дереве → `ScriptSecurityError`, exec не вызывается
  - Вызовы `eval`, `exec`, `open`, `__import__`, `compile` → `ScriptSecurityError`
  - Имена `os`, `sys`, `subprocess`, `httpx`, `requests`, `socket` → `ScriptSecurityError`
- **Шаг 2 (ПОСЛЕ валидации):** `exec(script, ALLOWED_GLOBALS)` с `ALLOWED_GLOBALS` строго по ARCHITECTURE.md секция 8
- Результат содержит все поля: `date, campaign_id, impressions, clicks, spend, conversions`
- Если LLM вернул невалидный Python → `ScriptGenerationError` с логом (до AST)
- `response_format={"type": "json_object"}` передаётся в `LLMProvider.complete()`
- Тест явно проверяет: скрипт с `import os` → `ScriptSecurityError` (exec не вызывается)

**Контракт:** Предоставляет нормализованный DataFrame для задачи 2.3.

---

### Задача 2.3: JSONB-хранение + GIN-индексы + Materialized View

**Предусловие:** Задача 2.2 ✓, Задача 1.2 ✓

**Реализация:**
- Изменить: `backend/app/services/import_service.py` — сохранение нормализованных данных в `raw_metrics.normalized`
- Создать: `backend/alembic/versions/003_materialized_view.py` — `metrics_daily_mv`
- Создать: `backend/app/services/mv_refresh_service.py` — `REFRESH MATERIALIZED VIEW CONCURRENTLY`

**Тест:**
```
Файл: backend/tests/test_import.py::test_gin_index_performance
Проверяет: аналитический запрос с GIN-индексом < 50ms на 100k строк
Команда: pytest backend/tests/test_import.py::test_gin_index_performance -v
Ожидаемый assert:
  # Вставляем 100k строк в raw_metrics
  # EXPLAIN ANALYZE SELECT ... WHERE normalized @> '{"campaign_id": "X"}'
  start = time.monotonic()
  result = await db.execute(query)
  elapsed_ms = (time.monotonic() - start) * 1000
  assert elapsed_ms < 50, f"Query took {elapsed_ms}ms, expected < 50ms"
  # Проверяем план: "Bitmap Index Scan" (не "Seq Scan")
  explain = await db.execute(text(f"EXPLAIN {query_str}"))
  assert "Bitmap Index Scan" in explain_text or "Index Scan" in explain_text
```

**DoD:**
- `metrics_daily_mv` создан и обновляется `REFRESH CONCURRENTLY`
- **UNIQUE-индекс `idx_metrics_daily_mv_pk` создаётся в той же миграции `003_materialized_view.py`, что и MV, и ДО первого `REFRESH`** — иначе `REFRESH CONCURRENTLY` выбросит ошибку `cannot refresh concurrently`
- Тест явно проверяет: `REFRESH MATERIALIZED VIEW CONCURRENTLY metrics_daily_mv` выполняется без ошибки (т.е. UNIQUE-индекс уже существует к моменту вызова)
- GIN-индекс `idx_raw_metrics_campaign_gin` используется планировщиком (не Seq Scan)
- Аналитический запрос по `campaign_id` выполняется < 50ms на 100k строк
- `maintenance_work_mem` поднимается до `256MB` на время построения индексов

**Контракт:** Предоставляет `metrics_daily_mv` для Фазы 3 (агент читает из неё).

---

### Чекпоинт Фазы 2

```
git tag phase-2-complete
```

---

## ФАЗА 3: Агентный AI-Директор

### Задача 3.1: AnomalyState + Detection Node

**Предусловие:** Фаза 2 ✓

**Реализация:**
- Создать: `backend/app/agents/anomaly_state.py` (TypedDict из ARCHITECTURE.md секция 7.1)
- Создать: `backend/app/agents/nodes/detection_node.py` — z-score по z-score > 2.5σ через SQL на `metrics_daily_mv`
- Создать: `backend/app/agents/anomaly_graph.py` — LangGraph граф (START → detection → ...)

**Тест:**
```
Файл: backend/tests/test_agents.py::test_detection_node_finds_spike
Проверяет: искусственный выброс в данных → candidates не пустой
Команда: pytest backend/tests/test_agents.py::test_detection_node_finds_spike -v
Ожидаемый assert:
  # Вставляем 30 дней нормальных данных CTR ~2%, потом 1 день CTR=15%
  state = await detection_node(initial_state)
  assert len(state["candidates"]) >= 1
  spike = state["candidates"][0]
  assert spike["metric"] == "ctr"
  assert spike["z_score"] > 2.5
```

**DoD:**
- Detection Node использует только SQL (нет LLM-вызовов)
- Результат — список `AnomalyCandidate` с заполненными z_score, direction
- Нет импортов `langchain-openai`, `langchain-community`
- langgraph граф компилируется без ошибок (`graph.compile()`)

**Контракт:** Предоставляет `candidates` для задачи 3.2.

---

### Задача 3.2: Verification Node + HITL Gate

**Предусловие:** Задача 3.1 ✓

**Реализация:**
- Создать: `backend/app/agents/nodes/verification_node.py` — LLM через `LLMProvider.complete()` проверяет кандидатов
- Создать: `backend/app/agents/nodes/hitl_gate_node.py` — interrupt при budget_change > 20% или fraud
- Изменить: `backend/app/agents/anomaly_graph.py` — добавить узлы и переходы

**Тест:**
```
Файл: backend/tests/test_agents.py::test_hitl_interrupt_on_budget_change
Проверяет: граф останавливается при изменении бюджета > 20%
Команда: pytest backend/tests/test_agents.py::test_hitl_interrupt_on_budget_change -v
Ожидаемый assert:
  # Мокаем LLM → возвращает verified_anomaly с action="reduce_budget_25%"
  final_state = await run_graph(initial_state)
  assert final_state["pending_approval"] == True
  assert final_state["approval_payload"] is not None
  # Граф не выполнил Action Node (нет изменений в БД)
```

**DoD:**
- Verification Node вызывает только `LLMProvider.complete()`, не импортирует openai SDK
- При `budget_change > 20%` или `fraud=True` → `pending_approval=True`, граф остановлен
- `PUT /api/v1/agents/anomaly/{run_id}/approve` возобновляет граф
- Тест: имитация ошибки LLM → Verification Node возвращает `error`, граф завершается безопасно

**Контракт:** Предоставляет `/approve` эндпоинт для фронтенда (Фаза 4).

---

### Задача 3.3: Text-to-SQL инструмент (read-only)

**Предусловие:** Задача 3.1 ✓

**Реализация:**
- Создать: `backend/app/agents/tools/text_to_sql.py`
  - Read-only соединение к БД
  - Валидация: только SELECT (иначе `ReadOnlySQLError`)
  - Инструмент LangGraph: принимает `question: str` → возвращает `result: list[dict]`

**Тест:**
```
Файл: backend/tests/test_agents.py::test_text_to_sql_readonly
Проверяет: INSERT/UPDATE/DELETE → ReadOnlySQLError; SELECT → результат
Команда: pytest backend/tests/test_agents.py::test_text_to_sql_readonly -v
Ожидаемый assert:
  with pytest.raises(ReadOnlySQLError):
      await text_to_sql_tool("DROP TABLE projects")
  result = await text_to_sql_tool("SELECT campaign_id, ctr FROM metrics_daily_mv LIMIT 5")
  assert isinstance(result, list)
```

**DoD:**
- Любой не-SELECT запрос → `ReadOnlySQLError` (не выполняется)
- Соединение использует отдельного DB-пользователя с правами только `SELECT` на `metrics_daily_mv`
- SQL инъекции не проходят (параметризованные запросы)

**Контракт:** Предоставляет инструмент для Verification Node.

---

### Чекпоинт Фазы 3

```
git tag phase-3-complete
```

---

## ФАЗА 4: Server-Driven UI

### Задача 4.1: Dashboard API эндпоинты

**Предусловие:** Фаза 1 ✓ (RLS), Фаза 2 ✓ (metrics_daily_mv)

**Реализация:**
- Создать: `backend/app/schemas/dashboard.py` — `Widget` Pydantic-модель (из ARCHITECTURE.md секция 6.1)
- Создать: `backend/app/services/dashboard_service.py`
  - `get_widget_array(project_id, user_id, db) -> list[Widget]`
  - `save_layout(project_id, user_id, widgets, db) -> None`
- Создать: `backend/app/api/v1/endpoints/dashboard.py`
  - `GET /api/v1/projects/{id}/dashboard`
  - `PUT /api/v1/projects/{id}/dashboard/layout`

**Тест:**
```
Файл: backend/tests/test_dashboard.py::test_widget_array_contract
Проверяет: ответ соответствует JSON Schema виджета
Команда: pytest backend/tests/test_dashboard.py::test_widget_array_contract -v
Ожидаемый assert:
  response = client.get(f"/api/v1/projects/{project_id}/dashboard", headers=auth)
  assert response.status_code == 200
  widgets = response.json()["widgets"]
  assert len(widgets) > 0
  for w in widgets:
      assert all(k in w for k in ["i", "x", "y", "w", "h", "chart", "dataKey", "title"])
      assert w["chart"] in ["line", "bar", "pie", "area", "number"]
```

**DoD:**
- `GET /dashboard` → `{"widgets": [...]}` соответствующий схеме из ARCHITECTURE.md секция 6.1
- `PUT /dashboard/layout` сохраняет в `dashboard_layouts` с RLS
- Изменение `chart` типа виджета в БД → следующий GET возвращает новый тип (без пересборки фронта)
- Данные виджетов приходят из `metrics_daily_mv`, не хардкодятся

**Контракт:** Предоставляет `widgetArray` API для фронтенда задачи 4.2.

---

### Задача 4.2: React Dashboard — ResponsiveReactGridLayout + Recharts

**Предусловие:** Задача 4.1 ✓

**Реализация:**
- Создать: `frontend/src/api/dashboard.ts` — TanStack Query хуки для GET/PUT
- Создать: `frontend/src/components/Dashboard/WidgetRenderer.tsx` — switch по `chart` типу → Recharts компонент в `ResponsiveContainer`
- Создать: `frontend/src/components/Dashboard/DashboardGrid.tsx` — `ResponsiveReactGridLayout` с `onLayoutChange` → PUT layout
- Изменить: `frontend/src/pages/ProjectDashboard.tsx` — интеграция

**Тест:**
```
Файл: frontend/src/components/Dashboard/__tests__/DashboardGrid.test.tsx
Проверяет: виджеты рендерятся из widgetArray; смена chart-типа отражается
Команда: cd frontend && npx vitest run src/components/Dashboard/__tests__/
Ожидаемый assert:
  // Мокаем API → возвращаем widgetArray с chart: "line"
  render(<DashboardGrid projectId="test-id" />)
  expect(screen.getByTestId("widget-line")).toBeInTheDocument()
  // Меняем мок → chart: "bar"
  rerender(...)
  expect(screen.getByTestId("widget-bar")).toBeInTheDocument()
```

**DoD:**
- Ресайз виджета мышкой → SVG-график перемасштабируется (ResponsiveContainer 100%/100%)
- `onLayoutChange` вызывает `PUT /dashboard/layout` с новыми координатами
- Фронтенд не содержит ни одной захардкоженной аналитической таблицы
- Смена `chart` типа в БД → после reload страницы новый тип виджета без пересборки React

**Контракт:** Финальная точка — полностью рабочий дашборд.

---

### Задача 4.3: ExportService

**Реализация:** Генерация .xlsx отчетов с формулами через openpyxl с помощью LLM. Нативная замена интеграции Google Sheets.

---

### Чекпоинт Фазы 4 (MVP Complete)

```
git tag mvp-complete
```

**Финальный критерий MVP:**
- Все фазы 1–4: все тесты зелёные
- Ревьюер проверил чеклист по всем задачам
- `docker compose up` поднимает всё окружение с нуля за < 2 минуты
- Демо-flow: регистрация → загрузка CSV → дашборд с виджетами → аномалия → HITL



## ФАЗА 5: Монетизация (после MVP, вне текущего плана)

> Реализуется после успешного демо MVP клиентам. Детализируется отдельным планом.

### Задачи (будут детализированы отдельно)

- **5.1** Подписки (trial / pro / enterprise) — таблица `subscriptions`
- **5.2** Token quota enforcement — лимит токенов на тенанта
- **5.3** Биллинг-дашборд — расходы по тенанту из `usage_logs`
- **5.4** Интеграция платёжного провайдера (CloudPayments / Stripe)

### Инфраструктура уже заложена в Фазах 1–3

```
✅ usage_logs таблица        — данные о потреблении LLM готовы (Фаза 1)
✅ tenants.plan поле         — готово к enforce в middleware (Фаза 1)
✅ LLMResponse.usage.cost_usd — стоимость каждого вызова пишется (Фаза 1/2)
```

### Для старта Фазы 5 нужно только

1. Добавить таблицу `subscriptions` с лимитами токенов per plan
2. Добавить middleware проверки:
   ```sql
   SELECT SUM(total_tokens) FROM usage_logs
   WHERE tenant_id = X AND created_at > month_start
   ```
   Если результат > `plan.token_limit` → HTTP 402 с сообщением о лимите
3. Подключить платёжный шлюз (Stripe или CloudPayments)

> **Почему сейчас не делаем:** Stripe/CloudPayments добавляет 2–3 недели интеграции.
> До MVP нет реальных клиентов → нет данных о правильных лимитах.
> `usage_logs` за период MVP покажет реальное потребление — это входные данные для ценообразования.
