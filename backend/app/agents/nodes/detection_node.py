import logging
from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.anomaly_state import AnomalyState, AnomalyCandidate

logger = logging.getLogger(__name__)

async def detection_node(state: AnomalyState, db: AsyncSession) -> AnomalyState:
    """
    Detection Node: Identifies anomalies (spikes/drops) in campaign metrics
    by computing historical z-scores directly via PostgreSQL over metrics_daily_mv.
    
    No LLM calls are allowed here (pure SQL).
    No DML queries (INSERT/UPDATE/DELETE) are allowed.
    """
    # 1. Initialize output state defaults
    state["candidates"] = []
    state["error"] = None
    
    try:
        # 2. Parse analysis_date string to Python datetime.date object for asyncpg compatibility
        analysis_date_str = state["analysis_date"]
        analysis_date_obj = date.fromisoformat(analysis_date_str)

        # 3. Strict RLS setup before running the query
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": state["tenant_id"]}
        )
        
        # 4. Composite SQL query to fetch statistical outliers for CTR, spend, conversions, impressions
        # Using standard SQL CAST() to prevent colon conflict with parameter prefix (:)
        query = text("""
            WITH stats AS (
                SELECT
                    campaign_id,
                    'ctr' AS metric,
                    AVG(ctr) AS mean_val,
                    STDDEV(ctr) AS std_val,
                    COUNT(*) AS sample_size
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date >= CAST(:analysis_date AS DATE) - INTERVAL '30 days'
                GROUP BY campaign_id
                HAVING COUNT(*) >= 30 AND STDDEV(ctr) > 0

                UNION ALL

                SELECT
                    campaign_id,
                    'spend' AS metric,
                    AVG(spend) AS mean_val,
                    STDDEV(spend) AS std_val,
                    COUNT(*) AS sample_size
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date >= CAST(:analysis_date AS DATE) - INTERVAL '30 days'
                GROUP BY campaign_id
                HAVING COUNT(*) >= 30 AND STDDEV(spend) > 0

                UNION ALL

                SELECT
                    campaign_id,
                    'conversions' AS metric,
                    AVG(conversions) AS mean_val,
                    STDDEV(conversions) AS std_val,
                    COUNT(*) AS sample_size
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date >= CAST(:analysis_date AS DATE) - INTERVAL '30 days'
                GROUP BY campaign_id
                HAVING COUNT(*) >= 30 AND STDDEV(conversions) > 0

                UNION ALL

                SELECT
                    campaign_id,
                    'impressions' AS metric,
                    AVG(impressions) AS mean_val,
                    STDDEV(impressions) AS std_val,
                    COUNT(*) AS sample_size
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date >= CAST(:analysis_date AS DATE) - INTERVAL '30 days'
                GROUP BY campaign_id
                HAVING COUNT(*) >= 30 AND STDDEV(impressions) > 0
            ),
            latest AS (
                SELECT campaign_id, 'ctr' AS metric, ctr AS current_value, date
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date = CAST(:analysis_date AS DATE)

                UNION ALL

                SELECT campaign_id, 'spend' AS metric, spend AS current_value, date
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date = CAST(:analysis_date AS DATE)

                UNION ALL

                SELECT campaign_id, 'conversions' AS metric, conversions AS current_value, date
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date = CAST(:analysis_date AS DATE)

                UNION ALL

                SELECT campaign_id, 'impressions' AS metric, impressions AS current_value, date
                FROM metrics_daily_mv
                WHERE tenant_id = CAST(:tenant_id AS UUID)
                  AND project_id = CAST(:project_id AS UUID)
                  AND date = CAST(:analysis_date AS DATE)
            )
            SELECT
                l.campaign_id,
                l.metric,
                l.current_value AS value,
                (l.current_value - s.mean_val) / s.std_val AS z_score,
                CAST(l.date AS TEXT) AS date
            FROM latest l
            JOIN stats s ON l.campaign_id = s.campaign_id AND l.metric = s.metric
            WHERE ABS((l.current_value - s.mean_val) / s.std_val) > 2.5
        """)
        
        result = await db.execute(
            query,
            {
                "tenant_id": state["tenant_id"],
                "project_id": state["project_id"],
                "analysis_date": analysis_date_obj
            }
        )
        
        rows = result.fetchall()
        candidates = []
        for row in rows:
            campaign_id, metric, value, z_score, date_str = row
            direction = "spike" if z_score > 0 else "drop"
            
            candidate = AnomalyCandidate(
                metric=metric,
                campaign_id=campaign_id,
                date=date_str,
                value=float(value),
                z_score=float(z_score),
                direction=direction
            )
            candidates.append(candidate)
            
        state["candidates"] = candidates
        
    except Exception as e:
        logger.error(f"Error in detection_node: {e}", exc_info=True)
        state["error"] = str(e)
        state["candidates"] = []
        
    return state
