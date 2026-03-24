"""API routes for runs."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ...runs.service import RunService
from ...runs.executor import RunExecutor
from ...runs.schemas import (
    RunCreateRequest,
    RunResponse,
    RunListResponse,
    RunCancelRequest,
    RunResumeRequest,
    WorktreeResponse
)
from ...db.session import get_db
import asyncio

router = APIRouter()


def get_run_service(db: Session = Depends(get_db)) -> RunService:
    """Get run service with database session."""
    return RunService(db)


@router.post("", response_model=dict)
def create_run(
    req: RunCreateRequest,
    background_tasks: BackgroundTasks,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    service: RunService = Depends(get_run_service),
    db: Session = Depends(get_db)
):
    """Create a new coding run and start execution.
    
    Args:
        req: Run creation request
        background_tasks: FastAPI background tasks
        x_user_id: User creating the run
        service: Run service
        db: Database session
        
    Returns:
        Created run with ID and state
    """
    result = service.create_run(req, created_by=x_user_id)
    
    # Start execution in background
    run_id = result["id"]
    executor = RunExecutor(db)
    
    # TODO: Set up orchestrator/retrieval/worker adapters
    # For now, execution will use default implementations
    
    background_tasks.add_task(_execute_run_async, executor, run_id)
    
    return {"run_id": result["id"], "state": result["state"]}


async def _execute_run_async(executor: RunExecutor, run_id: UUID):
    """Async wrapper for run execution."""
    await executor.execute_run(run_id)


@router.get("", response_model=RunListResponse)
def list_runs(
    repo_id: Optional[str] = Query(None, description="Filter by repository"),
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: RunService = Depends(get_run_service)
):
    """List runs with optional filtering.
    
    Args:
        repo_id: Filter by repository
        state: Filter by run state
        limit: Maximum results
        offset: Pagination offset
        service: Run service
        
    Returns:
        List of runs
    """
    result = service.list_runs(repo_id=repo_id, state=state, limit=limit, offset=offset)
    return RunListResponse(runs=result["runs"], total=result["total"])


@router.get("/{run_id}", response_model=dict)
def get_run(
    run_id: UUID,
    service: RunService = Depends(get_run_service)
):
    """Get run by ID.
    
    Args:
        run_id: Run UUID
        service: Run service
        
    Returns:
        Run details
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.post("/{run_id}/cancel", response_model=dict)
def cancel_run(
    run_id: UUID,
    req: RunCancelRequest,
    service: RunService = Depends(get_run_service)
):
    """Cancel a run.
    
    Args:
        run_id: Run UUID
        req: Cancel request
        service: Run service
        
    Returns:
        Updated run state
    """
    try:
        result = service.cancel(run_id, reason=req.reason)
        return {"run_id": result["id"], "state": result["state"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{run_id}/resume", response_model=dict)
def resume_run(
    run_id: UUID,
    req: RunResumeRequest,
    service: RunService = Depends(get_run_service),
    db: Session = Depends(get_db)
):
    """Resume a paused or waiting run.
    
    Args:
        run_id: Run UUID
        req: Resume request
        service: Run service
        db: Database session
        
    Returns:
        Updated run state
    """
    try:
        result = service.resume(run_id, from_step=req.from_step)
        
        # If resuming from waiting_approval, check if patch is now approved
        if result["state"] == "waiting_approval":
            executor = RunExecutor(db)
            background_tasks = BackgroundTasks()
            background_tasks.add_task(executor.resume_run, run_id)
        
        return {"run_id": result["id"], "state": result["state"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{run_id}/worktree", response_model=dict)
def get_worktree(
    run_id: UUID,
    service: RunService = Depends(get_run_service)
):
    """Get worktree for a run.
    
    Args:
        run_id: Run UUID
        service: Run service
        
    Returns:
        Worktree details
    """
    worktree = service.get_worktree(run_id)
    if not worktree:
        raise HTTPException(status_code=404, detail=f"No worktree found for run {run_id}")
    return worktree


@router.post("/{run_id}/execute", response_model=dict)
def execute_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger run execution.
    
    This is useful for re-running a run that failed or was interrupted.
    
    Args:
        run_id: Run UUID
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Execution started confirmation
    """
    from ...runs.models import Run
    
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if run.state not in ("created", "failed", "cancelled"):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot execute run in state '{run.state}'. Must be created, failed, or cancelled."
        )
    
    executor = RunExecutor(db)
    background_tasks.add_task(_execute_run_async, executor, run_id)
    
    return {
        "run_id": str(run_id),
        "status": "execution_started",
        "previous_state": run.state
    }
