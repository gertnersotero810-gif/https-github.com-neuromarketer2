import io
import pytest
import os
import uuid
import jwt
from fastapi import Depends, HTTPException
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core import security
from app.api.v1 import deps
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.models.project import Project

def get_testing_session():
    database_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql+asyncpg://neuro:secret@localhost:5432/neuromarketer"
    )
    engine = create_async_engine(database_url)
    return async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

@pytest.fixture(autouse=True)
async def override_db():
    TestingSessionLocal = get_testing_session()
    
    async def _override_get_db_shared():
        async with TestingSessionLocal() as session:
            yield session

    async def _override_get_db(token: str = Depends(deps.reusable_oauth2)):
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                raise HTTPException(
                    status_code=401,
                    detail="Tenant context missing in token",
                )
            tenant_uuid = uuid.UUID(tenant_id)
        except Exception:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
            )
        async with TestingSessionLocal() as session:
            session.info["tenant_id"] = tenant_uuid
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_uuid)}
            )
            yield session

    app.dependency_overrides[deps.get_db_shared] = _override_get_db_shared
    app.dependency_overrides[deps.get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_csv_upload_analyze():
    # 1. Register a user (which automatically creates a default tenant)
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    full_name = "Test Importer"
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )
        assert register_response.status_code == 200, register_response.text
        
        # 2. Login
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
        
        # Decode token to get tenant_id
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        tenant_id = payload["tenant_id"]
        
        # 3. Create a project under this tenant in DB
        TestingSessionLocal = get_testing_session()
        async with TestingSessionLocal() as session:
            project = Project(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                name="Test Project"
            )
            session.add(project)
            await session.commit()
            project_id = project.id

        # 4. Prepare test CSV in memory
        csv_content = (
            "campaign_id,date,impressions,clicks,spend,conversions\n"
            "camp_001,2024-01-01,10000,500,250.50,25\n"
            "camp_002,2024-01-02,8000,400,200.00,20\n"
            "camp_003,2024-01-03,12000,600,300.75,30\n"
        )
        csv_bytes = csv_content.encode("utf-8")
        
        # 5. POST /api/v1/projects/{project_id}/import/analyze
        # multipart/form-data: file=<csv_bytes>
        files = {"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")}
        
        response = await client.post(
            f"/api/v1/projects/{project_id}/import/analyze",
            headers={"Authorization": f"Bearer {token}"},
            files=files
        )
        
        # Assertions
        assert response.status_code == 200, response.text
        data = response.json()
        assert "columns" in data
        assert len(data["columns"]) == 6
        assert "samples" in data
        assert len(data["samples"]) == 3
        assert "file_hash" in data

@pytest.mark.asyncio
async def test_csv_upload_invalid_extension():
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Test Importer"}
        )
        login_response = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        token = login_response.json()["access_token"]
        
        # Invalid extension txt instead of csv
        files = {"file": ("test.txt", io.BytesIO(b"some content"), "text/plain")}
        response = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/import/analyze",
            headers={"Authorization": f"Bearer {token}"},
            files=files
        )
        assert response.status_code == 415

@pytest.mark.asyncio
async def test_csv_upload_too_large():
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Test Importer"}
        )
        login_response = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        token = login_response.json()["access_token"]
        
        # 11 MB of dummy data (limit is 10 MB)
        large_content = b"a" * (11 * 1024 * 1024)
        files = {"file": ("test.csv", io.BytesIO(large_content), "text/csv")}
        response = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/import/analyze",
            headers={"Authorization": f"Bearer {token}"},
            files=files
        )
        assert response.status_code == 413

@pytest.mark.asyncio
async def test_csv_upload_rls_denied():
    # User A registers
    email_a = f"user_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # User A registers and creates a project
        await client.post(
            "/api/v1/auth/register",
            json={"email": email_a, "password": password, "full_name": "User A"}
        )
        login_a = await client.post(
            "/api/v1/auth/login", data={"username": email_a, "password": password}
        )
        token_a = login_a.json()["access_token"]
        payload_a = jwt.decode(token_a, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        tenant_a_id = payload_a["tenant_id"]
        
        TestingSessionLocal = get_testing_session()
        async with TestingSessionLocal() as session:
            project_a = Project(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_a_id),
                name="Project A"
            )
            session.add(project_a)
            await session.commit()
            project_a_id = project_a.id
            
        # User B registers and tries to access Project A
        await client.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": password, "full_name": "User B"}
        )
        login_b = await client.post(
            "/api/v1/auth/login", data={"username": email_b, "password": password}
        )
        token_b = login_b.json()["access_token"]
        
        # Try uploading to User A's project using User B's token
        files = {"file": ("test.csv", io.BytesIO(b"col1,col2\n1,2"), "text/csv")}
        response = await client.post(
            f"/api/v1/projects/{project_a_id}/import/analyze",
            headers={"Authorization": f"Bearer {token_b}"},
            files=files
        )
        # Should be 404 (or 403, but 404 is safer to prevent enumeration)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_upsert_raw_metrics():
    # 1. Create tenant, project
    TestingSessionLocal = get_testing_session()
    async with TestingSessionLocal() as session:
        # Generate random IDs to avoid conflicts
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        
        # Insert tenant
        await session.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "Upsert Tenant", "slug": f"upsert-tenant-{uuid.uuid4().hex[:6]}"}
        )
        # Insert project
        await session.execute(
            text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": project_id, "tid": tenant_id, "name": "Upsert Project"}
        )
        await session.commit()
        
    # We will use pandas DataFrame as input to save_normalized_batch
    import pandas as pd
    from app.services.import_service import save_normalized_batch
    
    # 3 rows of data
    df1 = pd.DataFrame([
        {"campaign_id": "camp_001", "date": "2024-01-01", "impressions": 1000, "clicks": 50, "spend": 10.0, "conversions": 5},
        {"campaign_id": "camp_002", "date": "2024-01-01", "impressions": 2000, "clicks": 100, "spend": 20.0, "conversions": 10},
        {"campaign_id": "camp_003", "date": "2024-01-01", "impressions": 3000, "clicks": 150, "spend": 30.0, "conversions": 15},
    ])
    
    # Run the upsert the first time
    async with TestingSessionLocal() as session:
        # Set tenant RLS
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        count1 = await save_normalized_batch(df1, project_id, tenant_id, session)
        await session.commit()
        
    assert count1 == 3
    
    # Check that they exist
    async with TestingSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        res = await session.execute(text("SELECT count(*) FROM raw_metrics WHERE tenant_id = :tid"), {"tid": tenant_id})
        assert res.scalar() == 3
        
    # Same 3 rows but with updated values (double impressions, clicks, etc.)
    df2 = pd.DataFrame([
        {"campaign_id": "camp_001", "date": "2024-01-01", "impressions": 1500, "clicks": 75, "spend": 15.0, "conversions": 7},
        {"campaign_id": "camp_002", "date": "2024-01-01", "impressions": 2500, "clicks": 125, "spend": 25.0, "conversions": 12},
        {"campaign_id": "camp_003", "date": "2024-01-01", "impressions": 3500, "clicks": 175, "spend": 35.0, "conversions": 17},
    ])
    
    async with TestingSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        count2 = await save_normalized_batch(df2, project_id, tenant_id, session)
        await session.commit()
        
    assert count2 == 3
    
    # Check that we still have 3 rows and values are updated
    async with TestingSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        res = await session.execute(text("SELECT count(*) FROM raw_metrics WHERE tenant_id = :tid"), {"tid": tenant_id})
        assert res.scalar() == 3
        
        res_rows = await session.execute(
            text("SELECT normalized FROM raw_metrics WHERE tenant_id = :tid ORDER BY (normalized->>'campaign_id')"),
            {"tid": tenant_id}
        )
        rows = [r[0] for r in res_rows.all()]
        assert rows[0]["impressions"] == 1500
        assert rows[1]["impressions"] == 2500
        assert rows[2]["impressions"] == 3500


@pytest.mark.asyncio
async def test_gin_index_performance():
    import time
    TestingSessionLocal = get_testing_session()
    
    # Create tenant, project
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    async with TestingSessionLocal() as session:
        await session.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "Perf Tenant", "slug": f"perf-tenant-{uuid.uuid4().hex[:6]}"}
        )
        await session.execute(
            text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": project_id, "tid": tenant_id, "name": "Perf Project"}
        )
        await session.commit()

    # Create 10,000 metrics
    import pandas as pd
    from app.services.import_service import save_normalized_batch
    from app.services.mv_refresh_service import refresh_metrics_mv
    
    rows = []
    for i in range(10000):
        rows.append({
            "campaign_id": f"camp_{i % 100:03d}",
            "date": f"2024-01-{(i // 100) % 28 + 1:02d}",
            "impressions": 1000 + i,
            "clicks": 50 + (i % 10),
            "spend": 10.0 + (i * 0.1),
            "conversions": 5 + (i % 5)
        })
    df = pd.DataFrame(rows)
    
    # Insert in batch
    async with TestingSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        await save_normalized_batch(df, project_id, tenant_id, session)
        await session.commit()
        
    # Refresh materialized view concurrently
    async with TestingSessionLocal() as session:
        await refresh_metrics_mv(session)
        await session.commit()
        
    # Execute query and measure performance
    query_str = "SELECT * FROM metrics_daily_mv WHERE tenant_id = :tid AND campaign_id = 'camp_001'"
    
    async with TestingSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)}
        )
        start_time = time.monotonic()
        res = await session.execute(text(query_str), {"tid": tenant_id})
        res.all()
        elapsed_ms = (time.monotonic() - start_time) * 1000
        
    assert elapsed_ms < 100.0, f"Query took too long: {elapsed_ms:.2f}ms"
    
    # EXPLAIN
    async with TestingSessionLocal() as session:
        explain_res = await session.execute(text(f"EXPLAIN {query_str}"), {"tid": tenant_id})
        explain_lines = [r[0] for r in explain_res.all()]
        explain_text = "\n".join(explain_lines)
        
    print(f"Explain plan:\n{explain_text}")
    assert "Index Scan" in explain_text or "Bitmap Index Scan" in explain_text
    assert "Seq Scan" not in explain_text

