"""Pydantic schemas for runs API."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime


class RunCreateRequest(BaseModel):
    """Request to create a new run."""
    repo_id: str = Field(..., description="Repository identifier")
    task_type: str = Field(..., description="Type of task (e.g., fix_failing_test)")
    goal: str = Field(..., description="Human-readable task description")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Runtime constraints")
    worker_profile: str = Field(default="gsd-default", description="Worker profile to use")


class RunResponse(BaseModel):
    """Run response model."""
    id: UUID
    repo_id: str
    task_type: str
    goal: str
    state: str
    worker_profile: str
    constraints: Dict[str, Any]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """List of runs response."""
    runs: List[RunResponse]
    total: int


class RunStateTransition(BaseModel):
    """State transition request."""
    target_state: str = Field(..., description="Target state to transition to")
    reason: Optional[str] = Field(None, description="Reason for transition")


class RunCancelRequest(BaseModel):
    """Cancel run request."""
    reason: Optional[str] = Field(None, description="Reason for cancellation")


class RunResumeRequest(BaseModel):
    """Resume run request."""
    from_step: Optional[int] = Field(None, description="Step to resume from")


class WorktreeResponse(BaseModel):
    """Worktree response model."""
    id: UUID
    run_id: UUID
    repo_id: str
    path: str
    branch_name: Optional[str]
    base_ref: Optional[str]
    status: str
    created_at: datetime
    released_at: Optional[datetime]

    class Config:
        from_attributes = True
