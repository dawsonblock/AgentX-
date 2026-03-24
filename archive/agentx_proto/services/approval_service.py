"""Approval service - business logic for approvals."""

from typing import Optional, List
from sqlalchemy.orm import Session

from db.models import Approval, Patch
from core.logging import get_logger

logger = get_logger(__name__)


class ApprovalService:
    """Service for managing approvals."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def record(
        self,
        run_id: str,
        patch_id: str,
        decision: str,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> Approval:
        """Record an approval decision.
        
        Args:
            run_id: Parent run ID
            patch_id: Patch being approved/rejected
            decision: 'approve' or 'reject'
            reason: Optional reason
            actor_id: Optional actor identifier
            
        Returns:
            Created Approval instance
        """
        approval = Approval(
            run_id=run_id,
            patch_id=patch_id,
            decision=decision,
            reason=reason,
            actor_id=actor_id
        )
        self.db.add(approval)
        
        # Update patch status
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        if patch:
            if decision == "approve":
                patch.status = "approved"
            else:
                patch.status = "rejected"
        
        self.db.commit()
        self.db.refresh(approval)
        logger.info(f"Recorded {decision} for patch {patch_id}")
        return approval
    
    def get(self, approval_id: str) -> Optional[Approval]:
        """Get an approval by ID."""
        return self.db.query(Approval).filter(Approval.id == approval_id).first()
    
    def list_for_run(self, run_id: str) -> List[Approval]:
        """List all approvals for a run."""
        return self.db.query(Approval).filter(Approval.run_id == run_id).order_by(Approval.created_at.desc()).all()
    
    def list_for_patch(self, patch_id: str) -> List[Approval]:
        """List all approvals for a patch."""
        return self.db.query(Approval).filter(Approval.patch_id == patch_id).order_by(Approval.created_at.desc()).all()
    
    def is_approved(self, patch_id: str) -> bool:
        """Check if a patch is approved."""
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        return patch is not None and patch.status == "approved"
