import pytest
from app.db.session import engine

@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()
