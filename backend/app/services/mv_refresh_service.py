from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def refresh_metrics_mv(db: AsyncSession) -> None:
    """
    Refreshes the metrics_daily_mv Materialized View concurrently.
    """
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY metrics_daily_mv;"))
