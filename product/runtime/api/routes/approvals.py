"""API routes for approvals."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Body, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.session import get_db

router = APIRouter()


class ApprovalDecision(BaseModel):
    """Approval decision request."""
    decision: str  # approve, reject
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval response."""
    approval_id: str
    run_id: str
    patch_id: str
    decision: str
    actor_id: str
    created_at: str


@router.get("/run/{run_id}")
def get_run_approvals(
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """Get approvals for a run.
    
    Args:
        run_id: Run UUID
        db: Database session
        
    Returns:
        List of approvals
    """
    # Placeholder - will implement with approval service
    return {
        "run_id": str(run_id),
        "approvals": [],
        "count": 0
    }


@router.get("/{approval_id}")
def get_approval(
    approval_id: UUID,
    db: Session = Depends(get_db)
):
    """Get approval by ID.
    
    Args:
        approval_id: Approval UUID
        db: Database session
        
    Returns:
        Approval details
    """
    # Placeholder - will implement with approval service
    raise ValueError(f"Approval {approval_id} not found")


@router.post("/run/{run_id}/patch/{patch_id}")
def submit_approval(
    run_id: UUID,
    patch_id: UUID,
    req: ApprovalDecision,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    db: Session = Depends(get_db)
):
    """Submit approval decision for a patch.
    
    Args:
        run_id: Run UUID
        patch_id: Patch UUID
        req: Approval decision
        x_user_id: User making the decision
        db: Database session
        
    Returns:
        Created approval record
    """
    if not x_user_id:
        raise ValueError("User ID is required for approval decisions")
    
    # Placeholder - will implement with approval service
    return {
        "run_id": str(run_id),
        "patch_id": str(patch_id),
        "decision": req.decision,
        "reason": req.reason,
        "actor_id": x_user_id
    }
