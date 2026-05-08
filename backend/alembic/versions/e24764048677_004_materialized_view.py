"""004_materialized_view

Revision ID: e24764048677
Revises: a18551e9610e
Create Date: 2026-05-08 04:52:10.149069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e24764048677'
down_revision: Union[str, None] = 'a18551e9610e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # c) Установить maintenance_work_mem на время миграции:
    op.execute("SET maintenance_work_mem = '256MB';")

    # a) Создать UNIQUE индекс на expression-полях для поддержки ON CONFLICT в raw_metrics
    op.execute("""
        CREATE UNIQUE INDEX uq_raw_metrics_normalized_fields 
        ON raw_metrics (tenant_id, project_id, (normalized->>'campaign_id'), (normalized->>'date'));
    """)

    # b) Создать GIN-индекс:
    op.execute("""
        CREATE INDEX idx_raw_metrics_normalized_gin
        ON raw_metrics USING GIN (normalized jsonb_path_ops);
    """)

    # d) Создать Materialized View:
    op.execute("""
        CREATE MATERIALIZED VIEW metrics_daily_mv AS
        SELECT
            tenant_id,
            project_id,
            (normalized->>'campaign_id')::TEXT        AS campaign_id,
            (normalized->>'date')::DATE               AS date,
            SUM((normalized->>'impressions')::BIGINT)  AS impressions,
            SUM((normalized->>'clicks')::BIGINT)       AS clicks,
            SUM((normalized->>'spend')::NUMERIC)       AS spend,
            SUM((normalized->>'conversions')::INTEGER) AS conversions,
            ROUND(
                SUM((normalized->>'clicks')::NUMERIC) /
                NULLIF(SUM((normalized->>'impressions')::NUMERIC), 0) * 100,
                2
            ) AS ctr
        FROM raw_metrics
        GROUP BY tenant_id, project_id,
                 normalized->>'campaign_id', normalized->>'date'
        WITH NO DATA;
    """)

    # e) СРАЗУ после CREATE MV — создать UNIQUE-индекс
    # (обязательно ДО первого REFRESH CONCURRENTLY):
    op.execute("""
        CREATE UNIQUE INDEX idx_metrics_daily_mv_pk
        ON metrics_daily_mv (tenant_id, campaign_id, date);
    """)

    # f) Первый REFRESH (обычный, не CONCURRENTLY — MV пустая):
    op.execute("REFRESH MATERIALIZED VIEW metrics_daily_mv;")


def downgrade() -> None:
    # Drop Materialized View and its unique index
    op.execute("DROP MATERIALIZED VIEW IF EXISTS metrics_daily_mv;")

    # Drop GIN index on raw_metrics
    op.execute("DROP INDEX IF EXISTS idx_raw_metrics_normalized_gin;")

    # Drop Unique index on raw_metrics
    op.execute("DROP INDEX IF EXISTS uq_raw_metrics_normalized_fields;")

