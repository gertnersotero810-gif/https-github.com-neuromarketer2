import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.dashboard_layout import DashboardLayout
from app.schemas.dashboard import Widget

async def get_widget_array(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession
) -> List[Dict[str, Any]]:
    """
    Retrieve dashboard widgets layout data for a specific project and user.
    """
    result = await db.execute(
        select(DashboardLayout).where(
            DashboardLayout.project_id == project_id,
            DashboardLayout.user_id == user_id
        )
    )
    layout = result.scalars().first()
    if not layout:
        return []
    return layout.layout_data

async def save_layout(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    widgets: List[Widget],
    tenant_id: uuid.UUID,
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
    
    # Check if Widgets are Pydantic objects or dicts
    serialized_widgets = [
        w.dict() if hasattr(w, "dict") else w
        for w in widgets
    ]
    
    if layout:
        layout.layout_data = serialized_widgets
    else:
        layout = DashboardLayout(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            layout_data=serialized_widgets
        )
        db.add(layout)
    
    await db.commit()
