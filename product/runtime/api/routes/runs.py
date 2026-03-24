"""API routes for runs."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.orm import Session

from ...runs.service import RunService
from ...runs.schemas import (
    RunCreateRequest,
    RunResponse,
    RunListResponse,
    RunCancelRequest,
    RunResumeRequest,
    WorktreeResponse
)
from ...db.session import get_db

router = APIRouter()


def get_run_service(db: Session = Depends(get_db)) -> RunService:
    """Get run service with database session."""
    return RunService(db)


@router.post("", response_model=dict)
def create_run(
    req: RunCreateRequest,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    service: RunService = Depends(get_run_service)
):
    """Create a new coding run.
    
    Args:
        req: Run creation request
        x_user_id: User creating the run
        service: Run service
        
    Returns:
        Created run with ID and state
    """
    result = service.create_run(req, created_by=x_user_id)
    return {"run_id": result["id"], "state": result["state"]}


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
        raise ValueError(f"Run {run_id} not found")
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
    result = service.cancel(run_id, reason=req.reason)
    return {"run_id": result["id"], "state": result["state"]}


@router.post("/{run_id}/resume", response_model=dict)
def resume_run(
    run_id: UUID,
    req: RunResumeRequest,
    service: RunService = Depends(get_run_service)
):
    """Resume a paused or waiting run.
    
    Args:
        run_id: Run UUID
        req: Resume request
        service: Run service
        
    Returns:
        Updated run state
    """
    result = service.resume(run_id, from_step=req.from_step)
    return {"run_id": result["id"], "state": result["state"]}


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
        raise ValueError(f"No worktree found for run {run_id}")
    return worktree
