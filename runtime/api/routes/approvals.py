"""API routes for approvals."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Body, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...approvals.service import ApprovalService
from ...runs.service import RunService
from ...db.session import get_db

router = APIRouter()


class ApprovalDecision(BaseModel):
    """Approval decision request."""
    decision: str  # approve, reject
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval response."""
    id: UUID
    run_id: UUID
    patch_id: UUID
    decision: str
    reason: Optional[str]
    actor_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    """Get approval service with database session."""
    return ApprovalService(db)


def get_run_service(db: Session = Depends(get_db)) -> RunService:
    """Get run service with database session."""
    return RunService(db)


@router.get("/run/{run_id}", response_model=dict)
def get_run_approvals(
    run_id: UUID,
    service: ApprovalService = Depends(get_approval_service)
):
    """Get approvals for a run.
    
    Args:
        run_id: Run UUID
        service: Approval service
        
    Returns:
        List of approvals
    """
    approvals = service.list_approvals_for_run(run_id)
    return {
        "run_id": str(run_id),
        "approvals": [a.to_dict() for a in approvals],
        "count": len(approvals)
    }


@router.get("/{approval_id}", response_model=dict)
def get_approval(
    approval_id: UUID,
    service: ApprovalService = Depends(get_approval_service)
):
    """Get approval by ID.
    
    Args:
        approval_id: Approval UUID
        service: Approval service
        
    Returns:
        Approval details
    """
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return approval.to_dict()


@router.get("/patch/{patch_id}", response_model=dict)
def get_patch_approval(
    patch_id: UUID,
    service: ApprovalService = Depends(get_approval_service)
):
    """Get approval for a patch.
    
    Args:
        patch_id: Patch UUID
        service: Approval service
        
    Returns:
        Approval details or null
    """
    approval = service.get_approval_by_patch(patch_id)
    status = service.get_approval_status(patch_id)
    
    return {
        "patch_id": str(patch_id),
        "status": status,
        "approval": approval.to_dict() if approval else None
    }


@router.post("/run/{run_id}/patch/{patch_id}", response_model=dict)
def submit_approval(
    run_id: UUID,
    patch_id: UUID,
    req: ApprovalDecision,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    approval_service: ApprovalService = Depends(get_approval_service),
    run_service: RunService = Depends(get_run_service)
):
    """Submit approval decision for a patch.
    
    Args:
        run_id: Run UUID
        patch_id: Patch UUID
        req: Approval decision
        x_user_id: User making the decision
        approval_service: Approval service
        run_service: Run service
        
    Returns:
        Created approval record
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User ID is required for approval decisions")
    
    if req.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")
    
    try:
        approval = approval_service.record_approval(
            run_id=run_id,
            patch_id=patch_id,
            decision=req.decision,
            reason=req.reason,
            actor_id=x_user_id
        )
        
        # If approved, transition run state (executor will pick this up)
        if req.decision == "approve":
            # Note: In a real system, the executor would be notified
            # For now, just emit the event
            pass
        
        return approval.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patch/{patch_id}/status")
def get_approval_status(
    patch_id: UUID,
    service: ApprovalService = Depends(get_approval_service)
):
    """Get approval status for a patch.
    
    Args:
        patch_id: Patch UUID
        service: Approval service
        
    Returns:
        Status: pending | approved | rejected | unknown
    """
    status = service.get_approval_status(patch_id)
    is_approved = service.is_patch_approved(patch_id)
    is_rejected = service.is_patch_rejected(patch_id)
    
    return {
        "patch_id": str(patch_id),
        "status": status,
        "is_approved": is_approved,
        "is_rejected": is_rejected
    }
