"""
Task 1.1 — Infrastructure test.
TDD RED: this test must fail until FastAPI app + health endpoint are created.
"""
import os
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


def test_nginx_timeout_config():
    """Проверить, что файл nginx/nginx.conf существует и содержит строку proxy_read_timeout 120s."""
    nginx_conf_path = os.path.join(os.path.dirname(__file__), "../../nginx/nginx.conf")
    assert os.path.exists(nginx_conf_path), "nginx/nginx.conf не найден"
    
    with open(nginx_conf_path, "r") as f:
        content = f.read()
    
    assert "proxy_read_timeout    120s;" in content or "proxy_read_timeout 120s;" in content, "Таймаут proxy_read_timeout 120s не найден в nginx.conf"


def test_postgres_version():
    """Проверить, что в docker-compose.yml образ postgres содержит 16-alpine."""
    docker_compose_path = os.path.join(os.path.dirname(__file__), "../../docker-compose.yml")
    assert os.path.exists(docker_compose_path), "docker-compose.yml не найден"
    
    with open(docker_compose_path, "r") as f:
        content = f.read()
    
    assert "image: postgres:16-alpine" in content, "Образ postgres:16-alpine не найден в docker-compose.yml"
