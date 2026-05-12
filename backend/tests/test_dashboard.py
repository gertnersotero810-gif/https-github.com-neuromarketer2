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


@pytest.mark.asyncio
async def test_get_widget_array_logs_exception_on_failure(caplog):
    import logging
    from app.services import dashboard_service
    from unittest.mock import AsyncMock
    
    # We pass a mock AsyncSession that raises an error on select
    db_mock = AsyncMock()
    # First execute (layout fetch) returns an empty result
    db_mock.execute.side_effect = [
        AsyncMock(scalars=lambda: AsyncMock(first=lambda: None)),
        Exception("Materialized view is locked or uninitialized")
    ]
    
    # Run service method
    widgets = await dashboard_service.get_widget_array(
        project_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        db=db_mock
    )
    
    # Assert it fell back gracefully
    assert len(widgets) > 0
    # Assert exception was logged
    assert any("Failed to fetch metrics_daily_mv" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_save_layout_raises_value_error_if_project_missing():
    from app.services import dashboard_service
    from app.schemas.dashboard import Widget
    from unittest.mock import AsyncMock
    
    db_mock = AsyncMock()
    # First execute (layout fetch) returns None
    # Second execute (project fetch) returns None to simulate missing project
    db_mock.execute.side_effect = [
        AsyncMock(scalars=lambda: AsyncMock(first=lambda: None)),
        AsyncMock(scalars=lambda: AsyncMock(first=lambda: None))
    ]
    
    with pytest.raises(ValueError, match="not found — cannot save layout"):
        await dashboard_service.save_layout(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            widgets=[
                Widget(i="w1", x=0, y=0, w=2, h=2, chart="line", dataKey="val", title="T1")
            ],
            db=db_mock
        )

