import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.membership import UserTenantMembership

@pytest.fixture
async def auth_client():
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Register user
        register_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Test User"}
        )
        user_id = register_res.json()["id"]
        
        # Login
        login_res = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password}
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Retrieve tenant_id directly from DB membership
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserTenantMembership).where(UserTenantMembership.user_id == uuid.UUID(user_id))
            )
            membership = res.scalars().first()
            tenant_id = membership.tenant_id
            
        yield client, headers, tenant_id, uuid.UUID(user_id)

@pytest.mark.asyncio
async def test_get_dashboard_no_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/dashboard")
        assert response.status_code in (401, 403)

@pytest.mark.asyncio
async def test_get_dashboard_project_not_found(auth_client):
    client, headers, _, _ = auth_client
    response = await client.get(
        f"/api/v1/projects/{uuid.uuid4()}/dashboard",
        headers=headers
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_widget_array_schema(auth_client):
    client, headers, tenant_id, _ = auth_client
    
    # Create project using the existing DB session Local
    async with AsyncSessionLocal() as session:
        project = Project(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Dashboard Project"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

    response = await client.get(
        f"/api/v1/projects/{project_id}/dashboard",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "widgets" in data
    assert isinstance(data["widgets"], list)
    for w in data["widgets"]:
        for k in ["i", "x", "y", "w", "h", "chart", "dataKey", "title"]:
            assert k in w
        assert w["chart"] in {"line", "bar", "pie", "area", "number"}

@pytest.mark.asyncio
async def test_layout_persistence(auth_client):
    client, headers, tenant_id, _ = auth_client
    
    # Create project using the existing DB session Local
    async with AsyncSessionLocal() as session:
        project = Project(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Dashboard Project"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

    layout_payload = {
        "widgets": [
            {
                "i": "revenue",
                "x": 0,
                "y": 0,
                "w": 6,
                "h": 4,
                "chart": "line",
                "dataKey": "revenue",
                "title": "Revenue"
            }
        ]
    }
    
    put_response = await client.put(
        f"/api/v1/projects/{project_id}/dashboard/layout",
        headers=headers,
        json=layout_payload
    )
    assert put_response.status_code in (200, 201, 204)
    
    get_response = await client.get(
        f"/api/v1/projects/{project_id}/dashboard",
        headers=headers
    )
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert "widgets" in get_data
    widgets = get_data["widgets"]
    assert len(widgets) > 0
    
    widget = widgets[0]
    assert widget["i"] == "revenue"
