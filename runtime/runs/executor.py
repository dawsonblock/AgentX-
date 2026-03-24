"""Run Executor - orchestrates the full run lifecycle.

This is the core workflow engine - SINGLE AUTHORITY for execution.
"""

import asyncio
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from .models import Run, Worktree
from .service import RunService
from .state_machine import validate_transition
from ..events.store import EventStore
from ..patches.service import PatchService
from ..patches.validator import validate_patch
from ..approvals.service import ApprovalService
from ..artifacts.service import ArtifactService
from provenance.trace_writer.service import ProvenanceService

# Adapter imports
from adapters.orchestrator.interface import Orchestrator
from adapters.orchestrator.local import LocalOrchestrator
from adapters.retrieval.interface import Retrieval
from adapters.retrieval.simple import SimpleRetrieval
from adapters.worker.interface import Worker
from adapters.worker.dummy_worker import DummyWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RunExecutor:
    """Executes the full run lifecycle from creation to completion.
    
    SINGLE EXECUTION AUTHORITY - No other code executes logic.
    
    Flow:
    1. Queue
    2. Allocate worktree (orchestrator)
    3. Build context (retrieval)
    4. Execute worker
    5. Validate patch
    6. Persist patch
    7. Emit event
    8. Wait for approval
    9. Apply patch (orchestrator)
    10. Finalize
    """

    def __init__(
        self,
        db: Session,
        orchestrator: Optional[Orchestrator] = None,
        retrieval: Optional[Retrieval] = None,
        worker: Optional[Worker] = None
    ):
        """Initialize executor with database session and adapters.
        
        Args:
            db: Database session
            orchestrator: Orchestrator adapter (default: LocalOrchestrator)
            retrieval: Retrieval adapter (default: SimpleRetrieval)
            worker: Worker adapter (default: DummyWorker)
        """
        self.db = db
        self.run_service = RunService(db)
        self.patch_service = PatchService(db)
        self.approval_service = ApprovalService(db)
        self.artifact_service = ArtifactService(db)
        self.provenance_service = ProvenanceService(db)
        self.event_store = EventStore(db)
        
        # Inject adapters with defaults
        self.orchestrator = orchestrator or LocalOrchestrator()
        self.retrieval = retrieval or SimpleRetrieval()
        self.worker = worker or DummyWorker()

    async def execute_run(self, run_id: UUID) -> None:
        """Execute a run through its full lifecycle.
        
        This is the main entry point for run execution.
        
        Args:
            run_id: Run UUID to execute
        """
        logger.info(f"Starting execution for run {run_id}")
        
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.error(f"Run {run_id} not found")
            return
        
        worktree_path = None
        
        try:
            # Phase 1: Queue
            await self._transition_state(run, "queued")
            
            # Phase 2: Allocate worktree
            worktree_path = await self._allocate_worktree(run)
            
            # Phase 3: Build context
            context = await self._build_context(run, worktree_path)
            
            # Phase 4: Execute worker
            result = await self._execute_worker(run, context, worktree_path)
            
            # Phase 5: Handle result
            if result.get("patch"):
                await self._handle_patch_result(run, result, worktree_path)
            else:
                await self._handle_completion_without_patch(run, result)
                
        except Exception as e:
            logger.exception(f"Run {run_id} failed: {e}")
            await self._handle_failure(run, str(e))

    async def _transition_state(self, run: Run, new_state: str) -> None:
        """Transition run to new state with validation."""
        try:
            validate_transition(run.state, new_state)
            old_state = run.state
            run.state = new_state
            self.db.commit()
            
            self.event_store.append(
                run_id=run.id,
                event_type="RunStateChanged",
                payload={"old_state": old_state, "new_state": new_state}
            )
            
            logger.info(f"Run {run.id}: {old_state} -> {new_state}")
        except ValueError as e:
            logger.error(f"Invalid state transition for run {run.id}: {e}")
            raise

    async def _allocate_worktree(self, run: Run) -> str:
        """Allocate a worktree for the run."""
        await self._transition_state(run, "provisioning")
        
        # Use orchestrator adapter
        worktree_path = self.orchestrator.prepare_worktree(
            repo_id=run.repo_id,
            run_id=str(run.id)
        )
        
        # Get base commit
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )
        base_commit = result.stdout.strip()
        
        # Create worktree record
        worktree = Worktree(
            run_id=run.id,
            repo_id=run.repo_id,
            path=worktree_path,
            branch_name=f"agentx/run-{str(run.id)[:8]}",
            base_ref=base_commit,
            status="active"
        )
        
        self.db.add(worktree)
        self.db.commit()
        
        self.event_store.append(
            run_id=run.id,
            event_type="WorktreeAllocated",
            payload={"path": worktree_path, "base_commit": base_commit}
        )
        
        self.provenance_service.record_step(
            run_id=run.id,
            step_name="worktree_allocation",
            input_data={"repo_id": run.repo_id},
            output_data={"worktree_path": worktree_path, "base_commit": base_commit}
        )
        
        return worktree_path

    async def _build_context(self, run: Run, worktree_path: str) -> dict:
        """Build context for the run."""
        await self._transition_state(run, "context_building")
        
        # Use retrieval adapter
        context = self.retrieval.build_context(
            repo_path=worktree_path,
            task=run.goal
        )
        
        files_selected = [f["path"] for f in context.get("files", [])]
        
        self.provenance_service.record_context_building(
            run_id=run.id,
            task=run.goal,
            files_selected=files_selected,
            context_size=sum(f.get("size", 0) for f in context.get("files", [])),
            retrieval_method="simple"
        )
        
        logger.info(f"Built context with {context.get('file_count', 0)} files for run {run.id}")
        
        return context

    async def _execute_worker(self, run: Run, context: dict, worktree_path: str) -> dict:
        """Execute the worker for the run."""
        await self._transition_state(run, "running")
        
        # Use worker adapter
        result = self.worker.run(
            task=run.goal,
            context=context
        )
        
        self.provenance_service.record_step(
            run_id=run.id,
            step_name="worker_execution",
            input_data={"task": run.goal},
            output_data={"has_patch": bool(result.get("patch"))}
        )
        
        return result

    async def _handle_patch_result(self, run: Run, result: dict, worktree_path: str) -> None:
        """Handle worker result with patch."""
        patch_text = result["patch"]
        
        # Validate patch
        if not validate_patch(patch_text, worktree_path):
            logger.error(f"Patch validation failed for run {run.id}")
            await self._transition_state(run, "failed")
            return
        
        # Create patch record
        patch = self.patch_service.create_patch(
            run_id=run.id,
            worktree_id=str(run.id),
            base_commit=result.get("base_commit", "HEAD"),
            diff_text=patch_text,
            summary=result.get("summary")
        )
        
        self.provenance_service.record_patch_generation(
            run_id=run.id,
            patch_id=patch.id,
            base_commit=result.get("base_commit", "HEAD"),
            files_changed=[],
            generation_method="worker"
        )
        
        # Transition to waiting approval
        await self._transition_state(run, "waiting_approval")
        
        # Wait for approval
        await self._wait_for_approval(run, patch.id, worktree_path)

    async def _wait_for_approval(self, run: Run, patch_id: UUID, worktree_path: str) -> None:
        """Wait for patch approval."""
        logger.info(f"Run {run.id} waiting for approval of patch {patch_id}")
        
        max_wait_seconds = 3600  # 1 hour timeout
        poll_interval = 5
        waited = 0
        
        while waited < max_wait_seconds:
            if self.approval_service.is_patch_approved(patch_id):
                logger.info(f"Patch {patch_id} approved, applying...")
                await self._apply_approved_patch(run, patch_id, worktree_path)
                return
            elif self.approval_service.is_patch_rejected(patch_id):
                logger.info(f"Patch {patch_id} rejected")
                await self._transition_state(run, "failed")
                return
            
            await asyncio.sleep(poll_interval)
            waited += poll_interval
        
        logger.warning(f"Approval timeout for run {run.id}")
        await self._transition_state(run, "failed")

    async def _apply_approved_patch(self, run: Run, patch_id: UUID, worktree_path: str) -> None:
        """Apply an approved patch."""
        patch = self.patch_service.get_patch(patch_id)
        if not patch:
            logger.error(f"Patch {patch_id} not found")
            await self._transition_state(run, "failed")
            return
        
        # Use orchestrator to apply patch
        success = self.orchestrator.apply_patch(worktree_path, patch.diff_text)
        
        if success:
            self.patch_service.update_status(patch_id, "applied")
            logger.info(f"Patch {patch_id} applied successfully")
            await self._transition_state(run, "completed")
        else:
            logger.error(f"Failed to apply patch {patch_id}")
            await self._transition_state(run, "failed")

    async def _handle_completion_without_patch(self, run: Run, result: dict) -> None:
        """Handle completion without producing a patch."""
        logger.info(f"Run {run.id} completed without patch")
        await self._transition_state(run, "completed")

    async def _handle_failure(self, run: Run, error: str) -> None:
        """Handle run failure."""
        self.event_store.append(
            run_id=run.id,
            event_type="RunFailed",
            payload={"error": error}
        )
        
        try:
            await self._transition_state(run, "failed")
        except ValueError:
            pass
