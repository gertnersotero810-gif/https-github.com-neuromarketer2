"""002_rls_policies

Revision ID: dc86348d8aef
Revises: 97e153d8cbbb
Create Date: 2026-05-07 20:46:45.661698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc86348d8aef'
down_revision: Union[str, None] = '97e153d8cbbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RLS for user_tenant_memberships
    op.execute("ALTER TABLE user_tenant_memberships ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE user_tenant_memberships FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY memberships_tenant_isolation ON user_tenant_memberships
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
    """)

    # RLS for projects
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE projects FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY projects_tenant_isolation ON projects
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
    """)

    # RLS for raw_metrics
    op.execute("ALTER TABLE raw_metrics ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE raw_metrics FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY raw_metrics_tenant_isolation ON raw_metrics
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
    """)

    # RLS for dashboard_layouts
    op.execute("ALTER TABLE dashboard_layouts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE dashboard_layouts FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY dashboard_layouts_tenant_isolation ON dashboard_layouts
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
    """)

    # RLS for usage_logs
    op.execute("ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE usage_logs FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY usage_logs_tenant_isolation ON usage_logs
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
    """)


def downgrade() -> None:
    # Drop policies and disable RLS for user_tenant_memberships
    op.execute("DROP POLICY IF EXISTS memberships_tenant_isolation ON user_tenant_memberships;")
    op.execute("ALTER TABLE user_tenant_memberships DISABLE ROW LEVEL SECURITY;")

    # Drop policies and disable RLS for projects
    op.execute("DROP POLICY IF EXISTS projects_tenant_isolation ON projects;")
    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY;")

    # Drop policies and disable RLS for raw_metrics
    op.execute("DROP POLICY IF EXISTS raw_metrics_tenant_isolation ON raw_metrics;")
    op.execute("ALTER TABLE raw_metrics DISABLE ROW LEVEL SECURITY;")

    # Drop policies and disable RLS for dashboard_layouts
    op.execute("DROP POLICY IF EXISTS dashboard_layouts_tenant_isolation ON dashboard_layouts;")
    op.execute("ALTER TABLE dashboard_layouts DISABLE ROW LEVEL SECURITY;")

    # Drop policies and disable RLS for usage_logs
    op.execute("DROP POLICY IF EXISTS usage_logs_tenant_isolation ON usage_logs;")
    op.execute("ALTER TABLE usage_logs DISABLE ROW LEVEL SECURITY;")
