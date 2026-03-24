"""Run Executor - orchestrates the full run lifecycle.

This is the core workflow engine that drives runs from created → completed/failed.
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
from ..approvals.service import ApprovalService
from ..artifacts.service import ArtifactService
from ..provenance.trace_writer.service import ProvenanceService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RunExecutor:
    """Executes the full run lifecycle from creation to completion.
    
    This orchestrates:
    1. Worktree allocation
    2. Context building
    3. Worker execution
    4. Patch storage
    5. Approval waiting
    6. Patch application
    """

    def __init__(self, db: Session):
        """Initialize executor with database session."""
        self.db = db
        self.run_service = RunService(db)
        self.patch_service = PatchService(db)
        self.approval_service = ApprovalService(db)
        self.artifact_service = ArtifactService(db)
        self.provenance_service = ProvenanceService(db)
        self.event_store = EventStore(db)
        
        # These will be injected/set later
        self.orchestrator_adapter = None
        self.retrieval_service = None
        self.worker_factory = None

    def set_adapters(self, orchestrator, retrieval, worker_factory):
        """Set external service adapters.
        
        Args:
            orchestrator: Orchestrator adapter for worktrees/sessions
            retrieval: Retrieval service for context building
            worker_factory: Factory function to create workers
        """
        self.orchestrator_adapter = orchestrator
        self.retrieval_service = retrieval
        self.worker_factory = worker_factory

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
        
        try:
            # Phase 1: Queue
            await self._transition_state(run, "queued")
            
            # Phase 2: Allocate worktree
            await self._allocate_worktree(run)
            
            # Phase 3: Build context
            await self._build_context(run)
            
            # Phase 4: Execute worker
            result = await self._execute_worker(run)
            
            # Phase 5: Handle result
            if result.get("patch"):
                await self._handle_patch_result(run, result)
            else:
                await self._handle_completion_without_patch(run, result)
                
        except Exception as e:
            logger.exception(f"Run {run_id} failed: {e}")
            await self._handle_failure(run, str(e))

    async def _transition_state(self, run: Run, new_state: str) -> None:
        """Transition run to new state with validation.
        
        Args:
            run: Run object
            new_state: Target state
        """
        try:
            validate_transition(run.state, new_state)
            old_state = run.state
            run.state = new_state
            self.db.commit()
            
            self.event_store.append(
                run_id=run.id,
                event_type="RunStateChanged",
                payload={
                    "old_state": old_state,
                    "new_state": new_state
                }
            )
            
            logger.info(f"Run {run.id}: {old_state} -> {new_state}")
        except ValueError as e:
            logger.error(f"Invalid state transition for run {run.id}: {e}")
            raise

    async def _allocate_worktree(self, run: Run) -> Worktree:
        """Allocate a worktree for the run.
        
        Args:
            run: Run object
            
        Returns:
            Worktree object
        """
        await self._transition_state(run, "provisioning")
        
        if not self.orchestrator_adapter:
            raise RuntimeError("Orchestrator adapter not set")
        
        # Call orchestrator to allocate worktree
        # This would normally be an async call to the TypeScript adapter
        # For now, we'll create a local worktree record
        import os
        import subprocess
        import uuid as uuid_module
        
        worktree_root = "/var/lib/product/worktrees"
        os.makedirs(worktree_root, exist_ok=True)
        
        worktree_path = os.path.join(worktree_root, str(run.id))
        branch_name = f"product/run-{str(run.id)[:8]}"
        
        # Clone the repository
        # In production, this would call the orchestrator adapter
        repo_path = f"/repos/{run.repo_id}"  # Assume local repos
        
        try:
            # Clone repo to worktree path
            subprocess.run(
                ["git", "clone", repo_path, worktree_path],
                check=True,
                capture_output=True,
                timeout=120
            )
            
            # Create and checkout branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=worktree_path,
                check=True,
                capture_output=True
            )
            
            # Get base commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            base_commit = result.stdout.strip()
            
        except Exception as e:
            logger.error(f"Failed to allocate worktree: {e}")
            raise
        
        # Create worktree record
        worktree = Worktree(
            run_id=run.id,
            repo_id=run.repo_id,
            path=worktree_path,
            branch_name=branch_name,
            base_ref=base_commit,
            status="active"
        )
        
        self.db.add(worktree)
        self.db.commit()
        
        self.event_store.append(
            run_id=run.id,
            event_type="WorktreeAllocated",
            payload={
                "worktree_id": str(worktree.id),
                "path": worktree_path,
                "branch": branch_name
            }
        )
        
        self.provenance_service.record_step(
            run_id=run.id,
            step_name="worktree_allocation",
            input_data={"repo_id": run.repo_id},
            output_data={
                "worktree_path": worktree_path,
                "branch": branch_name,
                "base_commit": base_commit
            }
        )
        
        return worktree

    async def _build_context(self, run: Run) -> dict:
        """Build context for the run.
        
        Args:
            run: Run object
            
        Returns:
            Context dictionary
        """
        await self._transition_state(run, "context_building")
        
        # Get worktree
        worktree = self.db.query(Worktree).filter(Worktree.run_id == run.id).first()
        if not worktree:
            raise RuntimeError("No worktree found for run")
        
        # Build context using retrieval service
        # For now, return a basic context structure
        context = {
            "task": run.goal,
            "worktree_path": worktree.path,
            "files": [],  # Would be populated by retrieval service
            "task_type": run.task_type
        }
        
        self.provenance_service.record_context_building(
            run_id=run.id,
            task=run.goal,
            files_selected=[],
            context_size=0,
            retrieval_method="basic"
        )
        
        return context

    async def _execute_worker(self, run: Run) -> dict:
        """Execute the worker for the run.
        
        Args:
            run: Run object
            
        Returns:
            Worker result dictionary
        """
        await self._transition_state(run, "running")
        
        # Get worktree
        worktree = self.db.query(Worktree).filter(Worktree.run_id == run.id).first()
        if not worktree:
            raise RuntimeError("No worktree found for run")
        
        # Create worker
        if not self.worker_factory:
            raise RuntimeError("Worker factory not set")
        
        worker = self.worker_factory(run.id)
        
        # Build context
        context = {
            "task": run.goal,
            "worktree_path": worktree.path,
            "task_type": run.task_type
        }
        
        # Start worker
        task_spec = {
            "goal": run.goal,
            "task_type": run.task_type,
            "constraints": run.constraints_json or {}
        }
        
        worker.start(task_spec, worktree.path, context)
        
        # Execute worker steps
        max_steps = run.constraints_json.get("max_steps", 50) if run.constraints_json else 50
        
        for step in range(max_steps):
            result = worker.step()
            
            # Record provenance for each step
            self.provenance_service.record_step(
                run_id=run.id,
                step_name=f"worker_step_{step}",
                input_data={"step": step},
                output_data={
                    "action": result.action.value,
                    "state": result.state.value
                }
            )
            
            # Check if worker completed or failed
            if result.state.value in ("completed", "failed"):
                break
            
            # Check for patch proposal
            if result.action.value == "submit_patch":
                patch_data = result.payload.get("patch", {})
                return {
                    "patch": patch_data.get("diff_text", ""),
                    "summary": patch_data.get("summary", ""),
                    "files": patch_data.get("files", []),
                    "worktree_path": worktree.path,
                    "base_commit": worktree.base_ref
                }
        
        # No patch produced
        return {
            "patch": None,
            "completed": True
        }

    async def _handle_patch_result(self, run: Run, result: dict) -> None:
        """Handle worker result with patch.
        
        Args:
            run: Run object
            result: Worker result with patch
        """
        # Create patch record
        worktree = self.db.query(Worktree).filter(Worktree.run_id == run.id).first()
        
        patch = self.patch_service.create_patch(
            run_id=run.id,
            worktree_id=str(worktree.id) if worktree else "",
            base_commit=result.get("base_commit", "HEAD"),
            diff_text=result["patch"],
            summary=result.get("summary")
        )
        
        self.provenance_service.record_patch_generation(
            run_id=run.id,
            patch_id=patch.id,
            base_commit=result.get("base_commit", "HEAD"),
            files_changed=[f.get("path") for f in result.get("files", [])],
            generation_method="worker"
        )
        
        # Transition to waiting approval
        await self._transition_state(run, "waiting_approval")
        
        # Wait for approval (poll)
        await self._wait_for_approval(run, patch.id)

    async def _wait_for_approval(self, run: Run, patch_id: UUID) -> None:
        """Wait for patch approval.
        
        Args:
            run: Run object
            patch_id: Patch UUID
        """
        logger.info(f"Run {run.id} waiting for approval of patch {patch_id}")
        
        # Poll for approval (in production, use webhooks or async notifications)
        max_wait_seconds = 3600  # 1 hour timeout
        poll_interval = 5  # 5 seconds
        waited = 0
        
        while waited < max_wait_seconds:
            # Check approval status
            if self.approval_service.is_patch_approved(patch_id):
                logger.info(f"Patch {patch_id} approved, applying...")
                await self._apply_approved_patch(run, patch_id)
                return
            elif self.approval_service.is_patch_rejected(patch_id):
                logger.info(f"Patch {patch_id} rejected")
                await self._transition_state(run, "failed")
                return
            
            await asyncio.sleep(poll_interval)
            waited += poll_interval
        
        # Timeout
        logger.warning(f"Approval timeout for run {run.id}")
        await self._transition_state(run, "failed")

    async def _apply_approved_patch(self, run: Run, patch_id: UUID) -> None:
        """Apply an approved patch.
        
        Args:
            run: Run object
            patch_id: Patch UUID
        """
        worktree = self.db.query(Worktree).filter(Worktree.run_id == run.id).first()
        if not worktree:
            logger.error(f"No worktree found for run {run.id}")
            await self._transition_state(run, "failed")
            return
        
        # Apply the patch
        success = self.patch_service.apply_patch_to_worktree(patch_id, worktree.path)
        
        if success:
            logger.info(f"Patch {patch_id} applied successfully")
            await self._transition_state(run, "completed")
        else:
            logger.error(f"Failed to apply patch {patch_id}")
            await self._transition_state(run, "failed")

    async def _handle_completion_without_patch(self, run: Run, result: dict) -> None:
        """Handle completion without producing a patch.
        
        Args:
            run: Run object
            result: Worker result
        """
        logger.info(f"Run {run.id} completed without patch")
        await self._transition_state(run, "completed")

    async def _handle_failure(self, run: Run, error: str) -> None:
        """Handle run failure.
        
        Args:
            run: Run object
            error: Error message
        """
        self.event_store.append(
            run_id=run.id,
            event_type="RunFailed",
            payload={"error": error}
        )
        
        try:
            await self._transition_state(run, "failed")
        except ValueError:
            # Already in terminal state
            pass

    async def resume_run(self, run_id: UUID) -> None:
        """Resume a paused or waiting run.
        
        Args:
            run_id: Run UUID
        """
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.error(f"Run {run_id} not found")
            return
        
        if run.state == "waiting_approval":
            # Find the patch and check if it's now approved
            from ..patches.service import PatchService
            patch_service = PatchService(self.db)
            patches = patch_service.list_patches_for_run(run_id)
            
            for patch in patches:
                if patch.status == "approved":
                    await self._apply_approved_patch(run, patch.id)
                    return
                elif patch.status == "rejected":
                    await self._transition_state(run, "failed")
                    return
        elif run.state == "paused":
            await self._transition_state(run, "running")
            # Continue execution...
