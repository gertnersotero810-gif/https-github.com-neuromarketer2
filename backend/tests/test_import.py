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
