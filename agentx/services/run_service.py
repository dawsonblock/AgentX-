"""Run service - business logic for runs."""

from typing import Optional, List
from sqlalchemy.orm import Session

from db.models import Run
from core.logging import get_logger

logger = get_logger(__name__)


class RunService:
    """Service for managing runs."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, task: str, repo: str) -> Run:
        """Create a new run.
        
        Args:
            task: Task description
            repo: Repository URL or path
            
        Returns:
            Created Run instance
        """
        run = Run(task=task, repo=repo)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(f"Created run {run.id}")
        return run
    
    def get(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""
        return self.db.query(Run).filter(Run.id == run_id).first()
    
    def list_all(self, limit: int = 100) -> List[Run]:
        """List all runs."""
        return self.db.query(Run).order_by(Run.created_at.desc()).limit(limit).all()
    
    def update_state(self, run_id: str, state: str) -> Optional[Run]:
        """Update run state."""
        run = self.get(run_id)
        if run:
            run.state = state
            self.db.commit()
            self.db.refresh(run)
        return run
    
    def set_worktree(self, run_id: str, worktree_path: str) -> Optional[Run]:
        """Set worktree path for a run."""
        run = self.get(run_id)
        if run:
            run.worktree_path = worktree_path
            self.db.commit()
            self.db.refresh(run)
        return run
