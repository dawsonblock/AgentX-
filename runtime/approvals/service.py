"""Approval service - business logic for approval workflow."""

from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session
import logging

from ..runs.models import Approval, Patch, Worktree, CICheck
from ..events.store import EventStore
from ..ci.service import get_service as get_ci_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApprovalService:
    """Service for managing approvals.
    
    Handles approval recording, retrieval, and patch approval state.
    Integrates with CI to run gates before approval.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.event_store = EventStore(db)
        self.ci_service = get_ci_service()

    def record_approval(
        self,
        run_id: UUID,
        patch_id: UUID,
        decision: str,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None,
        skip_ci: bool = False
    ) -> Approval:
        """Record an approval decision.
        
        If decision is 'approve' and skip_ci is False, CI checks will be run first.
        
        Args:
            run_id: Run UUID
            patch_id: Patch UUID
            decision: 'approve' or 'reject'
            reason: Optional reason for the decision
            actor_id: User making the decision
            skip_ci: Skip CI checks (for emergency approvals)
            
        Returns:
            Created Approval object
            
        Raises:
            ValueError: If decision is not 'approve' or 'reject'
        """
        if decision not in ('approve', 'reject'):
            raise ValueError(f"Invalid decision: {decision}. Must be 'approve' or 'reject'")
        
        # If approving, run CI checks first (unless skipped)
        if decision == 'approve' and not skip_ci:
            ci_passed = self._run_ci_checks(run_id, patch_id)
            if not ci_passed:
                logger.warning(f"CI checks failed for patch {patch_id}, blocking approval")
                raise ValueError("CI checks failed. Cannot approve patch.")
        
        # Create approval record
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
            if decision == 'approve':
                patch.status = 'approved'
            else:
                patch.status = 'rejected'
        
        self.db.commit()
        self.db.refresh(approval)
        
        # Emit approval event
        self.event_store.append(
            run_id=run_id,
            event_type="ApprovalSubmitted",
            payload={
                "approval_id": str(approval.id),
                "patch_id": str(patch_id),
                "decision": decision,
                "reason": reason,
                "actor_id": actor_id,
                "ci_skipped": skip_ci
            },
            actor_kind="user",
            actor_id=actor_id
        )
        
        return approval

    def _run_ci_checks(self, run_id: UUID, patch_id: UUID) -> bool:
        """Run CI checks on a patch.
        
        Args:
            run_id: Run UUID
            patch_id: Patch UUID
            
        Returns:
            True if all CI checks passed, False otherwise
        """
        # Get worktree path and patch
        worktree = self.db.query(Worktree).filter(Worktree.run_id == run_id).first()
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        
        if not worktree:
            logger.error(f"No worktree found for run {run_id}")
            return False
        
        if not patch:
            logger.error(f"No patch found for patch_id {patch_id}")
            return False
        
        # Detect repo type
        repo_type = self.ci_service.detect_repo_type(worktree.path)
        logger.info(f"Detected repo type: {repo_type} for run {run_id}")
        
        # Run CI checks (with diff for secrets scanning)
        ci_result = self.ci_service.run_ci_checks(
            worktree_path=worktree.path,
            patch_id=str(patch_id),
            repo_type=repo_type,
            diff_text=patch.diff_text
        )
        
        # Store CI results in database
        for gate in ci_result.gates:
            ci_check = CICheck(
                patch_id=patch_id,
                run_id=run_id,
                gate_name=gate.name,
                status=gate.status.value,
                exit_code=gate.exit_code,
                stdout=gate.stdout,
                stderr=gate.stderr,
                duration_ms=gate.duration_ms
            )
            self.db.add(ci_check)
        
        self.db.commit()
        
        # Emit CI completed event
        self.event_store.append(
            run_id=run_id,
            event_type="CICompleted",
            payload={
                "patch_id": str(patch_id),
                "overall_status": ci_result.overall_status.value,
                "summary": ci_result.summary,
                "gates": [
                    {
                        "name": g.name,
                        "status": g.status.value,
                        "duration_ms": g.duration_ms
                    }
                    for g in ci_result.gates
                ]
            }
        )
        
        logger.info(f"CI completed for patch {patch_id}: {ci_result.summary}")
        
        return ci_result.overall_status.value == 'passed'

    def get_approval(self, approval_id: UUID) -> Optional[Approval]:
        """Get approval by ID.
        
        Args:
            approval_id: Approval UUID
            
        Returns:
            Approval object or None
        """
        return self.db.query(Approval).filter(Approval.id == approval_id).first()

    def get_approval_by_patch(self, patch_id: UUID) -> Optional[Approval]:
        """Get the approval for a specific patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            Most recent Approval object or None
        """
        return self.db.query(Approval)\
            .filter(Approval.patch_id == patch_id)\
            .order_by(Approval.created_at.desc())\
            .first()

    def list_approvals_for_run(self, run_id: UUID) -> List[Approval]:
        """List all approvals for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            List of Approval objects
        """
        return self.db.query(Approval)\
            .filter(Approval.run_id == run_id)\
            .order_by(Approval.created_at.desc())\
            .all()

    def list_approvals_for_patch(self, patch_id: UUID) -> List[Approval]:
        """List all approvals for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            List of Approval objects
        """
        return self.db.query(Approval)\
            .filter(Approval.patch_id == patch_id)\
            .order_by(Approval.created_at.desc())\
            .all()

    def is_patch_approved(self, patch_id: UUID) -> bool:
        """Check if a patch has been approved.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            True if patch is approved, False otherwise
        """
        # Check the patch status directly
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        if patch:
            return patch.status == 'approved'
        return False

    def is_patch_rejected(self, patch_id: UUID) -> bool:
        """Check if a patch has been rejected.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            True if patch is rejected, False otherwise
        """
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        if patch:
            return patch.status == 'rejected'
        return False

    def get_approval_status(self, patch_id: UUID) -> str:
        """Get the approval status for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            Status string: 'pending', 'approved', 'rejected', or 'unknown'
        """
        patch = self.db.query(Patch).filter(Patch.id == patch_id).first()
        if not patch:
            return 'unknown'
        
        if patch.status == 'proposed':
            return 'pending'
        elif patch.status == 'approved':
            return 'approved'
        elif patch.status == 'rejected':
            return 'rejected'
        else:
            return patch.status

    def get_ci_checks_for_patch(self, patch_id: UUID) -> List[CICheck]:
        """Get CI checks for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            List of CICheck objects
        """
        return self.db.query(CICheck)\
            .filter(CICheck.patch_id == patch_id)\
            .order_by(CICheck.created_at.asc())\
            .all()

    def revoke_approval(self, approval_id: UUID, actor_id: Optional[str] = None) -> bool:
        """Revoke a previous approval (admin use).
        
        Args:
            approval_id: Approval UUID to revoke
            actor_id: User revoking the approval
            
        Returns:
            True if revoked, False if not found
        """
        approval = self.get_approval(approval_id)
        if not approval:
            return False
        
        # Note: We don't delete approvals, just mark them as superseded
        # The patch status would need to be reset separately
        
        self.event_store.append(
            run_id=approval.run_id,
            event_type="ApprovalRevoked",
            payload={
                "approval_id": str(approval_id),
                "original_decision": approval.decision
            },
            actor_kind="user",
            actor_id=actor_id
        )
        
        return True
