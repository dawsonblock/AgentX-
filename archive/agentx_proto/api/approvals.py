"""Approval API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.deps import get_db
from services.patch_service import PatchService
from services.approval_service import ApprovalService
from services.ci_service import CIService
from orchestrator import worktree
from worker.tools.git_tools import apply_patch

router = APIRouter()


class ApprovalRequest(BaseModel):
    """Approval request."""
    decision: str  # approve or reject
    reason: str = ""
    actor_id: str = "system"


class ApprovalResponse(BaseModel):
    """Approval response."""
    patch_id: str
    decision: str
    status: str


@router.post("/{patch_id}", response_model=ApprovalResponse)
def decide(patch_id: str, request: ApprovalRequest, db: Session = Depends(get_db)):
    """Make an approval decision on a patch.
    
    If approved, runs CI and applies patch on success.
    
    Args:
        patch_id: Patch ID
        request: Approval decision
        db: Database session
        
    Returns:
        Decision result
    """
    patch_svc = PatchService(db)
    approval_svc = ApprovalService(db)
    ci_svc = CIService()
    
    # Get patch
    patch = patch_svc.get(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    
    # Validate decision
    if request.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")
    
    # Record approval
    approval_svc.record(
        run_id=patch.run_id,
        patch_id=patch_id,
        decision=request.decision,
        reason=request.reason,
        actor_id=request.actor_id
    )
    
    if request.decision == "approve":
        # Allocate worktree and apply patch
        # In real implementation, use the original worktree
        try:
            wt = worktree.allocate(patch.run.repo if hasattr(patch, 'run') else ".")
            
            # Apply patch
            ok = apply_patch(wt, patch.diff)
            if not ok:
                patch_svc.set_status(patch_id, "failed")
                worktree.cleanup(wt)
                return ApprovalResponse(
                    patch_id=patch_id,
                    decision=request.decision,
                    status="apply_failed"
                )
            
            # Run CI
            ci_passed = ci_svc.run(wt)
            worktree.cleanup(wt)
            
            if ci_passed:
                patch_svc.set_status(patch_id, "applied")
                return ApprovalResponse(
                    patch_id=patch_id,
                    decision=request.decision,
                    status="applied"
                )
            else:
                patch_svc.set_status(patch_id, "ci_failed")
                return ApprovalResponse(
                    patch_id=patch_id,
                    decision=request.decision,
                    status="ci_failed"
                )
                
        except Exception as e:
            patch_svc.set_status(patch_id, "failed")
            raise HTTPException(status_code=500, detail=f"Approval processing failed: {e}")
    
    else:
        # Rejected
        patch_svc.set_status(patch_id, "rejected")
        return ApprovalResponse(
            patch_id=patch_id,
            decision=request.decision,
            status="rejected"
        )
