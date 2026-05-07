"""
Task 1.1 — Infrastructure test.
TDD RED: this test must fail until FastAPI app + health endpoint are created.
"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_check():
    """GET /api/v1/health must return 200 and {"status": "ok"}"""
    from app.main import app  # noqa: PLC0415 — import inside test is intentional

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
