"""RunExecutor - single authority for execution.

This is the ONLY place allowed to execute anything.
"""

from sqlalchemy.orm import Session

from runtime.state_machine import move
from runtime.event_store import EventStore
from runtime.policies import check_tool, check_steps
from core.logging import get_logger
from core.errors import WorkerError

logger = get_logger(__name__)


class ServiceBundle:
    """Bundle of services for executor."""
    
    def __init__(self, db: Session, **services):
        self.db = db
        for name, service in services.items():
            setattr(self, name, service)


class RunExecutor:
    """Execute runs through the full lifecycle.
    
    This is the single authority - no other code executes logic.
    """
    
    def __init__(self, db: Session, services: ServiceBundle):
        self.db = db
        self.s = services
    
    def execute(self, run_id: str):
        """Execute a run through its full lifecycle.
        
        Args:
            run_id: Run ID to execute
            
        Returns:
            Generated Patch
        """
        run = self.s.run.get(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Transition: created -> queued
        move(run, "queued")
        self.s.events.append(run.id, "state_changed", {"state": run.state})
        self.db.commit()
        
        # Allocate worktree
        worktree = self.s.orch.allocate(run.repo)
        self.s.run.set_worktree(run.id, worktree)
        
        # Transition: queued -> provisioning
        move(run, "provisioning")
        self.s.events.append(run.id, "state_changed", {"state": run.state, "worktree": worktree})
        self.db.commit()
        
        # Build context
        context = self.s.orch.build_context(worktree, run.task)
        
        # Transition: provisioning -> context
        move(run, "context")
        self.s.events.append(run.id, "state_changed", {"state": run.state, "context_files": len(context)})
        self.db.commit()
        
        # Record provenance
        self.s.prov.record(
            run_id=run.id,
            step="context_built",
            input_data={"task": run.task, "repo": run.repo},
            output_data={"context_files": len(context), "files": [c["path"] for c in context[:10]]}
        )
        
        # Execute worker
        try:
            result = self.s.worker.execute(run.task, context, worktree)
        except Exception as e:
            logger.error(f"Worker failed for run {run_id}: {e}")
            move(run, "failed")
            self.s.events.append(run.id, "worker_failed", {"error": str(e)})
            self.db.commit()
            raise WorkerError(f"Worker execution failed: {e}")
        
        # Transition: context -> running
        move(run, "running")
        self.s.events.append(run.id, "state_changed", {"state": run.state})
        self.db.commit()
        
        # Create patch
        patch = self.s.patch.create(
            run_id=run.id,
            diff=result.diff,
            summary=getattr(result, 'summary', None)
        )
        
        # Record provenance
        self.s.prov.record(
            run_id=run.id,
            step="patch_created",
            input_data={"worktree": worktree},
            output_data={"patch_id": patch.id, "diff_length": len(result.diff)}
        )
        
        # Transition: running -> waiting_approval
        move(run, "waiting_approval")
        self.s.events.append(run.id, "patch_created", {"patch_id": patch.id, "status": patch.status})
        self.db.commit()
        
        logger.info(f"Run {run_id} complete, waiting approval for patch {patch.id}")
        return patch
