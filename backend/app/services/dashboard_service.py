import uuid
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.dashboard_layout import DashboardLayout
from app.models.project import Project
from app.schemas.dashboard import Widget

async def get_widget_array(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession
) -> List[Dict[str, Any]]:
    """
    Retrieve dashboard widgets layout data for a specific project and user.
    If no custom layout is saved, generates a default set of widgets.
    Dynamically fetches aggregate metrics from metrics_daily_mv to populate widget data.
    """
    # 1. Fetch saved layout from database
    result = await db.execute(
        select(DashboardLayout).where(
            DashboardLayout.project_id == project_id,
            DashboardLayout.user_id == user_id
        )
    )
    layout = result.scalars().first()
    
    if layout:
        widgets = layout.layout_data
    else:
        # Default widgets layout if user hasn't saved a custom layout yet
        widgets = [
            {
                "i": "widget-ctr-01",
                "x": 0, "y": 0, "w": 6, "h": 4,
                "chart": "line",
                "dataKey": "ctr",
                "title": "CTR по дням"
            },
            {
                "i": "widget-spend-02",
                "x": 6, "y": 0, "w": 6, "h": 4,
                "chart": "bar",
                "dataKey": "spend",
                "title": "Расходы по кампаниям"
            },
            {
                "i": "widget-conversions-kpi-03",
                "x": 0, "y": 4, "w": 6, "h": 4,
                "chart": "area",
                "dataKey": "conversions",
                "title": "Конверсии в реальном времени"
            },
            {
                "i": "widget-cpc-04",
                "x": 6, "y": 4, "w": 6, "h": 4,
                "chart": "number",
                "dataKey": "cpc",
                "title": "Средний CPC"
            }
        ]

    # 2. Retrieve actual metrics from metrics_daily_mv (never hardcoded, per DoD)
    try:
        mv_result = await db.execute(
            text("""
                SELECT date, 
                       SUM(impressions) as impressions, 
                       SUM(clicks) as clicks, 
                       SUM(spend) as spend, 
                       SUM(conversions) as conversions
                FROM metrics_daily_mv
                WHERE project_id = :project_id
                GROUP BY date
                ORDER BY date ASC
            """),
            {"project_id": project_id}
        )
        rows = mv_result.fetchall()
        
        mv_data = []
        for r in rows:
            date_str = r.date.strftime("%Y-%m-%d") if hasattr(r.date, "strftime") else str(r.date)
            ctr = round((r.clicks / r.impressions) * 100, 2) if r.impressions and r.impressions > 0 else 0.0
            cpc = round(r.spend / r.clicks, 2) if r.clicks and r.clicks > 0 else 0.0
            
            mv_data.append({
                "name": date_str,
                "impressions": int(r.impressions) if r.impressions is not None else 0,
                "clicks": int(r.clicks) if r.clicks is not None else 0,
                "spend": float(r.spend) if r.spend is not None else 0.0,
                "conversions": int(r.conversions) if r.conversions is not None else 0,
                "ctr": ctr,
                "cpc": cpc
            })
    except Exception:
        # Fallback to empty list if view is empty or does not exist
        mv_data = []

    # 3. Inject the server-driven database metrics into the widgets
    populated_widgets = []
    for w in widgets:
        w_copy = dict(w)
        if mv_data:
            w_copy["data"] = mv_data
        populated_widgets.append(w_copy)

    return populated_widgets

async def save_layout(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    widgets: List[Widget],
    db: AsyncSession
) -> None:
    """
    Save or update dashboard widgets layout data.
    """
    result = await db.execute(
        select(DashboardLayout).where(
            DashboardLayout.project_id == project_id,
            DashboardLayout.user_id == user_id
        )
    )
    layout = result.scalars().first()
    
    # Use Pydantic's model_dump() to fix deprecation warning (2.2)
    serialized_widgets = [
        w.model_dump() if hasattr(w, "model_dump") else w
        for w in widgets
    ]
    
    if layout:
        layout.layout_data = serialized_widgets
    else:
        # Retrieve project tenant_id from database
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalars().first()
        tenant_id = project.tenant_id if project else None
        
        layout = DashboardLayout(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            layout_data=serialized_widgets
        )
        db.add(layout)
    
    await db.commit()
