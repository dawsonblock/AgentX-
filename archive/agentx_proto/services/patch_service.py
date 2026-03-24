"""Patch service - business logic for patches."""

from typing import Optional, List
from sqlalchemy.orm import Session

from db.models import Patch
from core.errors import ValidationError
from core.logging import get_logger

logger = get_logger(__name__)


class PatchService:
    """Service for managing patches."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        run_id: str,
        diff: str,
        summary: Optional[str] = None,
        base_commit: Optional[str] = None
    ) -> Patch:
        """Create a new patch.
        
        Args:
            run_id: Parent run ID
            diff: Git diff content
            summary: Optional summary
            base_commit: Optional base commit hash
            
        Returns:
            Created Patch instance
            
        Raises:
            ValidationError: If diff is empty
        """
        if not diff or not diff.strip():
            raise ValidationError("Cannot create patch: empty diff")
        
        patch = Patch(
            run_id=run_id,
            diff=diff,
            summary=summary,
            base_commit=base_commit
        )
        self.db.add(patch)
        self.db.commit()
        self.db.refresh(patch)
        logger.info(f"Created patch {patch.id} for run {run_id}")
        return patch
    
    def get(self, patch_id: str) -> Optional[Patch]:
        """Get a patch by ID."""
        return self.db.query(Patch).filter(Patch.id == patch_id).first()
    
    def list_for_run(self, run_id: str) -> List[Patch]:
        """List all patches for a run."""
        return self.db.query(Patch).filter(Patch.run_id == run_id).order_by(Patch.created_at.desc()).all()
    
    def set_status(self, patch_id: str, status: str) -> Optional[Patch]:
        """Update patch status."""
        patch = self.get(patch_id)
        if patch:
            patch.status = status
            self.db.commit()
            self.db.refresh(patch)
            logger.info(f"Patch {patch_id} status -> {status}")
        return patch
