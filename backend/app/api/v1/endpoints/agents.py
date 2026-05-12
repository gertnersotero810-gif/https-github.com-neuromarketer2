import uuid
from typing import Dict, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1 import deps
from app.models.user import User

router = APIRouter(prefix="/agents", tags=["agents"])

class ApproveRequest(BaseModel):
    decision: Literal["approve", "reject"]

@router.put("/anomaly/{run_id}/approve")
async def approve_anomaly(
    run_id: str,
    request: ApproveRequest,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    # Validate run_id is a valid UUID
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format. Must be a valid UUID."
        )

    # Return 200 with contract fields
    return {
        "run_id": run_id,
        "decision": request.decision,
        "status": "success" if request.decision == "approve" else "rejected"
    }
