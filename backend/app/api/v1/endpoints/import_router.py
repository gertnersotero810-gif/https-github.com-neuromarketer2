import io
import uuid
import hashlib
from typing import Any, Dict, List
import pandas as pd
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.v1 import deps
from app.models.user import User
from app.models.project import Project

router = APIRouter(tags=["import"])

# In-memory storage for import sessions as requested
import_sessions: Dict[str, Any] = {}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/projects/{project_id}/import/analyze")
async def analyze_csv(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, Any]:
    # 1. Validate file extension
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file format. Only CSV allowed."
        )

    # 2. Read file content to memory and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Max size is 10MB."
        )

    # 3. RLS check: Validate that project belongs to user's tenant
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format. Must be a valid UUID."
        )

    project_result = await db.execute(select(Project).where(Project.id == project_uuid))
    project = project_result.scalars().first()
    current_tenant_id = db.info.get("tenant_id")
    if not project or (current_tenant_id and project.tenant_id != current_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    # 4. Parse CSV using Pandas
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV file: {str(e)}"
        )

    row_count = len(df)

    # 5. Extract columns & calculate coverage
    columns_info = []
    for col in df.columns:
        coverage = (df[col].notna().sum() / row_count) if row_count > 0 else 0
        columns_info.append({
            "name": str(col),
            "low_coverage": bool(coverage < 0.6)
        })

    # 6. Extract head 3 samples, replacing NaN/None for JSON compatibility
    df_samples = df.head(3).replace({np.nan: None})
    samples = df_samples.to_dict(orient="records")

    # 7. Generate file hash
    file_hash = hashlib.sha256(content).hexdigest()

    # 8. Save session in-memory
    import_sessions[file_hash] = {
        "columns": [str(c) for c in df.columns],
        "samples": samples,
        "project_id": str(project_id),
        "row_count": row_count
    }

    return {
        "columns": columns_info,
        "samples": samples,
        "file_hash": file_hash,
        "row_count": row_count
    }
