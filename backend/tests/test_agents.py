import os
import pytest
import uuid
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import from our application modules (this will fail initially, which is expected for RED phase)
from app.agents.anomaly_state import AnomalyState
from app.agents.nodes.detection_node import detection_node
from app.services.import_service import save_normalized_batch

@pytest.fixture
async def db_session():
    database_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql+asyncpg://neuro:secret@localhost:5432/neuromarketer"
    )
    engine = create_async_engine(database_url)
    TestingSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_detection_node_finds_spike(db_session: AsyncSession):
    # 1. Create tenant, project
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    
    # Insert tenant
    await db_session.execute(
        text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": tenant_id, "name": "Test Tenant Spike", "slug": f"test-tenant-{uuid.uuid4().hex[:6]}"}
    )
    # Insert project
    await db_session.execute(
        text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tid, :name)"),
        {"id": project_id, "tid": tenant_id, "name": "Test Project Spike"}
    )
    await db_session.commit()

    # 2. Insert into metrics_daily_mv via raw_metrics
    # - 30 days of normal data (CTR ~ 2%)
    # - 1 day of anomaly (the last one, today, CTR ~ 15%)
    rows = []
    # 30 normal days
    for i in range(30, 0, -1):
        metric_date = date.today() - timedelta(days=i)
        rows.append({
            "campaign_id": "camp_spike",
            "date": metric_date.isoformat(),
            "impressions": 10000,
            "clicks": 200,
            "spend": 500.0,
            "conversions": 20
        })
    # 1 anomaly day (today)
    rows.append({
        "campaign_id": "camp_spike",
        "date": date.today().isoformat(),
        "impressions": 10000,
        "clicks": 1500,
        "spend": 500.0,
        "conversions": 20
    })
    
    df = pd.DataFrame(rows)
    
    # Set RLS
    await db_session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tenant_id)}
    )
    
    await save_normalized_batch(df, project_id, tenant_id, db_session)
    await db_session.commit()
    
    # Refresh Materialized View (not CONCURRENTLY)
    await db_session.execute(text("REFRESH MATERIALIZED VIEW metrics_daily_mv;"))
    await db_session.commit()
    
    # 3. Execution
    initial_state = AnomalyState(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        analysis_date=date.today().isoformat(),
        metrics_snapshot=[],
        candidates=[],
        verified_anomalies=[],
        pending_approval=False,
        approval_payload=None,
        error=None,
    )
    
    result_state = await detection_node(initial_state, db=db_session)
    
    # 4. Assertions
    assert len(result_state["candidates"]) >= 1
    spike = result_state["candidates"][0]
    assert spike["metric"] == "ctr"
    assert spike["z_score"] > 2.5
    assert spike["direction"] == "spike"

@pytest.mark.asyncio
async def test_detection_node_insufficient_data(db_session: AsyncSession):
    # 1. Create tenant, project
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    
    # Insert tenant
    await db_session.execute(
        text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": tenant_id, "name": "Test Tenant Insufficient", "slug": f"test-tenant-{uuid.uuid4().hex[:6]}"}
    )
    # Insert project
    await db_session.execute(
        text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tid, :name)"),
        {"id": project_id, "tid": tenant_id, "name": "Test Project Insufficient"}
    )
    await db_session.commit()

    # 2. Insert only 5 days of data (< 30)
    rows = []
    for i in range(5, 0, -1):
        metric_date = date.today() - timedelta(days=i)
        rows.append({
            "campaign_id": "camp_insufficient",
            "date": metric_date.isoformat(),
            "impressions": 10000,
            "clicks": 200,
            "spend": 500.0,
            "conversions": 20
        })
    df = pd.DataFrame(rows)
    
    # Set RLS
    await db_session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tenant_id)}
    )
    
    await save_normalized_batch(df, project_id, tenant_id, db_session)
    await db_session.commit()
    
    # Refresh Materialized View (not CONCURRENTLY)
    await db_session.execute(text("REFRESH MATERIALIZED VIEW metrics_daily_mv;"))
    await db_session.commit()
    
    # 3. Execution
    initial_state = AnomalyState(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        analysis_date=date.today().isoformat(),
        metrics_snapshot=[],
        candidates=[],
        verified_anomalies=[],
        pending_approval=False,
        approval_payload=None,
        error=None,
    )
    
    result_state = await detection_node(initial_state, db=db_session)
    
    # 4. Assertions
    assert result_state["candidates"] == []
    assert result_state["error"] is None


@pytest.mark.asyncio
async def test_verification_node_confirms_anomaly():
    from unittest.mock import AsyncMock
    from app.core.llm_provider import LLMResponse, UsageInfo
    from app.agents.nodes.verification_node import verification_node

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content='{"verified": true, "action": "reduce_budget", "budget_change_pct": 25, "fraud": false, "reasoning": "CTR drop detected"}',
        usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        model="gpt-4o-mini"
    )

    state = {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "analysis_date": "2024-01-01",
        "metrics_snapshot": [],
        "candidates": [{"metric": "ctr", "z_score": 3.1, "direction": "drop"}],
        "verified_anomalies": [],
        "pending_approval": False,
        "approval_payload": None,
        "error": None,
    }

    result = await verification_node(state, llm=mock_llm)

    assert mock_llm.complete.called
    assert len(result["verified_anomalies"]) == 1
    assert result["error"] is None


@pytest.mark.asyncio
async def test_verification_node_handles_llm_error():
    from unittest.mock import AsyncMock
    from app.agents.nodes.verification_node import verification_node

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = Exception("API timeout")

    state = {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "analysis_date": "2024-01-01",
        "metrics_snapshot": [],
        "candidates": [{"metric": "ctr", "z_score": 3.1, "direction": "drop"}],
        "verified_anomalies": [],
        "pending_approval": False,
        "approval_payload": None,
        "error": None,
    }

    result = await verification_node(state, llm=mock_llm)

    assert result["error"] is not None
    assert result["verified_anomalies"] == []


@pytest.mark.asyncio
async def test_hitl_gate_sets_pending_on_budget_change():
    from app.agents.nodes.hitl_gate_node import hitl_gate_node

    state = {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "analysis_date": "2024-01-01",
        "metrics_snapshot": [],
        "candidates": [],
        "verified_anomalies": [
            {"metric": "ctr", "budget_change_pct": 25, "fraud": False, "verified": True}
        ],
        "pending_approval": False,
        "approval_payload": None,
        "error": None,
    }

    result = await hitl_gate_node(state)

    assert result["pending_approval"] == True
    assert result["approval_payload"] is not None


@pytest.mark.asyncio
async def test_hitl_gate_sets_pending_on_fraud():
    from app.agents.nodes.hitl_gate_node import hitl_gate_node

    state = {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "analysis_date": "2024-01-01",
        "metrics_snapshot": [],
        "candidates": [],
        "verified_anomalies": [
            {"metric": "spend", "budget_change_pct": 5, "fraud": True, "verified": True}
        ],
        "pending_approval": False,
        "approval_payload": None,
        "error": None,
    }

    result = await hitl_gate_node(state)

    assert result["pending_approval"] == True
    assert result["approval_payload"] is not None


@pytest.mark.asyncio
async def test_hitl_gate_no_pending_on_safe_conditions():
    from app.agents.nodes.hitl_gate_node import hitl_gate_node

    state = {
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "analysis_date": "2024-01-01",
        "metrics_snapshot": [],
        "candidates": [],
        "verified_anomalies": [
            {"metric": "spend", "budget_change_pct": 10, "fraud": False, "verified": True}
        ],
        "pending_approval": False,
        "approval_payload": None,
        "error": None,
    }

    result = await hitl_gate_node(state)

    assert result["pending_approval"] == False
    assert result["approval_payload"] is None


@pytest.mark.asyncio
async def test_approve_endpoint_success():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "secretpassword"
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Test Approve User"
            }
        )
        assert register_response.status_code == 200, register_response.text

        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": password
            }
        )
        assert login_response.status_code == 200, login_response.text
        token_data = login_response.json()
        token = token_data["access_token"]

        run_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/v1/agents/anomaly/{run_id}/approve",
            json={"decision": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in (200, 202)
        data = response.json()
        assert data["run_id"] == run_id
        assert data["decision"] == "approve"
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_text_to_sql_readonly_checks():
    from app.agents.tools.text_to_sql import text_to_sql_tool, ReadOnlySQLError
    from unittest.mock import AsyncMock

    mock_db = AsyncMock()

    # 1. DROP TABLE raises ReadOnlySQLError
    with pytest.raises(ReadOnlySQLError):
        await text_to_sql_tool("DROP TABLE projects", mock_db)

    # 2. INSERT raises ReadOnlySQLError
    with pytest.raises(ReadOnlySQLError):
        await text_to_sql_tool("INSERT INTO raw_metrics (raw_data) VALUES ('{}')", mock_db)

    # 3. UPDATE raises ReadOnlySQLError
    with pytest.raises(ReadOnlySQLError):
        await text_to_sql_tool("UPDATE projects SET name = 'Hacked'", mock_db)


@pytest.mark.asyncio
async def test_text_to_sql_valid_select():
    from app.agents.tools.text_to_sql import text_to_sql_tool
    from unittest.mock import AsyncMock, MagicMock

    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    mock_row1 = {"campaign_id": "c1", "ctr": 0.05}
    mock_row2 = {"campaign_id": "c2", "ctr": 0.02}
    
    mock_result.mappings.return_value.all.return_value = [mock_row1, mock_row2]
    mock_db.execute.return_value = mock_result

    result = await text_to_sql_tool("SELECT campaign_id, ctr FROM metrics_daily_mv", mock_db)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["campaign_id"] == "c1"
    assert result[1]["ctr"] == 0.02

