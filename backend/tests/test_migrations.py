"""
Test that Alembic migrations create the correct tables.
TDD RED phase: this test must fail because there are no tables yet.
"""
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


@pytest.mark.asyncio
async def test_database_tables_exist():
    database_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql+asyncpg://neuro:secret@localhost:5432/neuromarketer"
    )
    
    engine = create_async_engine(database_url)
    
    expected_tables = ["tenants", "users", "user_tenant_memberships", "projects"]
    found_tables = []
    
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        found_tables = [row[0] for row in result.fetchall()]
        
    missing_tables = [t for t in expected_tables if t not in found_tables]
    
    assert not missing_tables, f"Missing tables: {missing_tables}"
