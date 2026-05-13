import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.v1 import deps
from app.models.user import User
from app.models.project import Project
from app.schemas.dashboard import DashboardResponse, DashboardLayoutUpdate
from app.services import dashboard_service
from app.services.export_service import ExportService
from app.core.llm_provider import LLMProvider


router = APIRouter(tags=["dashboard"])

@router.get("/projects/{project_id}/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    project_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> DashboardResponse:
    # 1. Validate project UUID format
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format. Must be a valid UUID."
        )

    # 2. RLS Check: Project must exist and belong to current tenant
    project_result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = project_result.scalars().first()
    
    current_tenant_id = db.info.get("tenant_id")
    if not project or (current_tenant_id and project.tenant_id != current_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    # 3. Retrieve dashboard layout using service layer
    widgets = await dashboard_service.get_widget_array(
        project_id=project_uuid,
        user_id=current_user.id,
        db=db
    )

    return DashboardResponse(widgets=widgets)


@router.put("/projects/{project_id}/dashboard/layout", status_code=status.HTTP_200_OK)
async def update_dashboard_layout(
    project_id: str,
    layout_update: DashboardLayoutUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, str]:
    # 1. Validate project UUID format
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format. Must be a valid UUID."
        )

    # 2. RLS Check: Project must exist and belong to current tenant
    project_result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = project_result.scalars().first()
    
    current_tenant_id = db.info.get("tenant_id")
    if not project or (current_tenant_id and project.tenant_id != current_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    # 3. Save layout using service layer
    await dashboard_service.save_layout(
        project_id=project_uuid,
        user_id=current_user.id,
        widgets=layout_update.widgets,
        db=db
    )

    return {
        "status": "saved",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/projects/{project_id}/dashboard/export")
async def export_dashboard(
    project_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
    llm: LLMProvider = Depends(deps.get_llm_provider)
) -> StreamingResponse:
    # 1. Validate project UUID format
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format. Must be a valid UUID."
        )

    # 2. RLS Check: Project must exist and belong to current tenant
    project_result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = project_result.scalars().first()
    
    current_tenant_id = db.info.get("tenant_id")
    if not project or (current_tenant_id and project.tenant_id != current_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    # 3. Retrieve widgets with populated data
    widgets = await dashboard_service.get_widget_array(
        project_id=project_uuid,
        user_id=current_user.id,
        db=db
    )

    # 4. Generate report bytes via ExportService
    xlsx_bytes = await ExportService.generate_report(
        widgets=widgets,
        project_name=project.name,
        tenant_id=str(project.tenant_id),
        llm=llm,
        db=db
    )

    # 5. Return StreamingResponse
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={project_id}_report.xlsx"
        }
    )

