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
