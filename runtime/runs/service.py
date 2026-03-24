"""Run service - business logic for run lifecycle."""

from uuid import UUID
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from .models import Run, Worktree
from .schemas import RunCreateRequest
from .state_machine import validate_transition, is_terminal_state
from ..events.store import EventStore
from ..db.session import get_db_session


class RunService:
    """Service for managing runs."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize service with optional database session."""
        self.db = db
        self._own_db = db is None
        self.event_store = EventStore(db)

    def _get_db(self) -> Session:
        """Get database session."""
        if self.db is None:
            self.db = get_db_session()
        return self.db

    def _close_db(self) -> None:
        """Close database session if we own it."""
        if self._own_db and self.db:
            self.db.close()
            self.db = None

    def create_run(self, req: RunCreateRequest, created_by: Optional[str] = None) -> Dict[str, Any]:
        """Create a new run.
        
        Args:
            req: Run creation request
            created_by: User creating the run
            
        Returns:
            Created run data
        """
        db = self._get_db()
        
        run = Run(
            repo_id=req.repo_id,
            task_type=req.task_type,
            goal=req.goal,
            state="created",
            worker_profile=req.worker_profile,
            constraints_json=req.constraints,
            created_by=created_by
        )
        
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Emit creation event
        self.event_store.append(
            run_id=run.id,
            event_type="RunCreated",
            payload={
                "repo_id": req.repo_id,
                "task_type": req.task_type,
                "worker_profile": req.worker_profile
            }
        )
        
        result = run.to_dict()
        return result

    def get_run(self, run_id: UUID) -> Optional[Dict[str, Any]]:
        """Get run by ID.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Run data or None if not found
        """
        db = self._get_db()
        run = db.query(Run).filter(Run.id == run_id).first()
        return run.to_dict() if run else None

    def list_runs(
        self,
        repo_id: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List runs with optional filtering.
        
        Args:
            repo_id: Filter by repository
            state: Filter by state
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of runs and total count
        """
        db = self._get_db()
        
        query = db.query(Run)
        
        if repo_id:
            query = query.filter(Run.repo_id == repo_id)
        if state:
            query = query.filter(Run.state == state)
        
        total = query.count()
        runs = query.order_by(Run.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "runs": [run.to_dict() for run in runs],
            "total": total
        }

    def transition_state(
        self,
        run_id: UUID,
        target_state: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transition run to new state.
        
        Args:
            run_id: Run UUID
            target_state: Target state
            reason: Optional reason for transition
            
        Returns:
            Updated run data
            
        Raises:
            ValueError: If transition is invalid
        """
        db = self._get_db()
        
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Validate transition
        validate_transition(run.state, target_state)
        
        old_state = run.state
        run.state = target_state
        db.commit()
        
        # Emit state change event
        self.event_store.append(
            run_id=run.id,
            event_type="RunStateChanged",
            payload={
                "old_state": old_state,
                "new_state": target_state,
                "reason": reason
            }
        )
        
        return run.to_dict()

    def cancel(self, run_id: UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a run.
        
        Args:
            run_id: Run UUID
            reason: Cancellation reason
            
        Returns:
            Updated run data
        """
        return self.transition_state(run_id, "cancelled", reason)

    def resume(self, run_id: UUID, from_step: Optional[int] = None) -> Dict[str, Any]:
        """Resume a paused or waiting run.
        
        Args:
            run_id: Run UUID
            from_step: Optional step to resume from
            
        Returns:
            Updated run data
        """
        db = self._get_db()
        
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Determine target state based on current state
        if run.state == "paused":
            target_state = "running"
        elif run.state == "waiting_approval":
            target_state = "running"
        else:
            raise ValueError(f"Cannot resume run in state '{run.state}'")
        
        return self.transition_state(run_id, target_state, f"Resumed from step {from_step}" if from_step else "Resumed")

    def create_worktree(
        self,
        run_id: UUID,
        repo_id: str,
        path: str,
        branch_name: str,
        base_ref: str
    ) -> Dict[str, Any]:
        """Record a worktree allocation for a run.
        
        Args:
            run_id: Run UUID
            repo_id: Repository ID
            path: Filesystem path to worktree
            branch_name: Git branch name
            base_ref: Base git ref
            
        Returns:
            Created worktree data
        """
        db = self._get_db()
        
        worktree = Worktree(
            run_id=run_id,
            repo_id=repo_id,
            path=path,
            branch_name=branch_name,
            base_ref=base_ref,
            status="active"
        )
        
        db.add(worktree)
        db.commit()
        db.refresh(worktree)
        
        # Emit worktree allocated event
        self.event_store.append(
            run_id=run_id,
            event_type="WorktreeAllocated",
            payload={
                "worktree_id": str(worktree.id),
                "path": path,
                "branch_name": branch_name,
                "base_ref": base_ref
            }
        )
        
        return worktree.to_dict()

    def get_worktree(self, run_id: UUID) -> Optional[Dict[str, Any]]:
        """Get worktree for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Worktree data or None
        """
        db = self._get_db()
        worktree = db.query(Worktree).filter(Worktree.run_id == run_id).first()
        return worktree.to_dict() if worktree else None
