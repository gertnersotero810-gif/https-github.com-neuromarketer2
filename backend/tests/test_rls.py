import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import uuid

@pytest.mark.asyncio
async def test_tenant_isolation():
    database_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql+asyncpg://neuro:secret@localhost:5432/neuromarketer"
    )
    engine = create_async_engine(database_url)
    
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    project_a_id = uuid.uuid4()
    project_b_id = uuid.uuid4()
    
    async with engine.begin() as conn:
        # Create tenants
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug) ON CONFLICT DO NOTHING"),
            [
                {"id": tenant_a_id, "name": "Tenant A", "slug": f"tenant-a-{tenant_a_id}"},
                {"id": tenant_b_id, "name": "Tenant B", "slug": f"tenant-b-{tenant_b_id}"}
            ]
        )
        
        # Create projects
        await conn.execute(
            text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tenant_id, :name) ON CONFLICT DO NOTHING"),
            [
                {"id": project_a_id, "tenant_id": tenant_a_id, "name": "Project A"},
                {"id": project_b_id, "tenant_id": tenant_b_id, "name": "Project B"}
            ]
        )

    # Create an app user for testing since neuro is a superuser and bypasses RLS
    async with engine.connect() as conn:
        try:
            async with conn.begin():
                await conn.execute(text("REASSIGN OWNED BY app_user TO neuro"))
                await conn.execute(text("DROP OWNED BY app_user"))
                await conn.execute(text("DROP ROLE IF EXISTS app_user"))
        except Exception:
            pass

        async with conn.begin():
            await conn.execute(text("CREATE ROLE app_user WITH LOGIN PASSWORD 'secret' NOSUPERUSER NOBYPASSRLS"))
            await conn.execute(text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user"))
            await conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user"))

    app_db_url = database_url.replace("neuro:secret", "app_user:secret")
    app_engine = create_async_engine(app_db_url)

    # Now test isolation
    async with app_engine.connect() as conn:
        # Start transaction for SET LOCAL to work
        async with conn.begin():
            # Set context using set_config which supports parameterization
            await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_a_id)})
            
            # Fetch projects
            result = await conn.execute(text("SELECT id FROM projects"))
            rows = result.fetchall()
            project_ids = [row[0] for row in rows]
            
            # Assertions
            assert project_a_id in project_ids, "Project A should be visible to Tenant A"
            assert project_b_id not in project_ids, "Project B should NOT be visible to Tenant A (RLS violation!)"
