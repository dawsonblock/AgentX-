"""GSD Wrapper Contracts

Defines the interface between the runtime and the GSD worker.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class WorkerState(Enum):
    """States for the GSD worker."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerAction(Enum):
    """Actions the worker can take."""
    REQUEST_TOOL = "request_tool"
    SUBMIT_PATCH = "submit_patch"
    SUBMIT_SUMMARY = "submit_summary"
    REQUEST_CLARIFICATION = "request_clarification"
    COMPLETE = "complete"
    FAIL = "fail"


@dataclass
class TaskSpec:
    """Specification for a task."""
    goal: str
    task_type: str
    constraints: Dict[str, Any]
    context_pack: Dict[str, Any]


@dataclass
class ToolRequest:
    """Request from worker to execute a tool."""
    tool_name: str
    args: Dict[str, Any]
    request_id: str


@dataclass
class ToolResponse:
    """Response to a tool request."""
    request_id: str
    result: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class PatchProposal:
    """Patch proposal from the worker."""
    format: str
    base_ref: str
    files: List[Dict[str, Any]]
    diff_text: str
    summary: Optional[str] = None


@dataclass
class WorkerStepResult:
    """Result of a worker step."""
    action: WorkerAction
    payload: Dict[str, Any]
    state: WorkerState
    step_number: int


@dataclass
class WorkerStatus:
    """Current worker status."""
    run_id: str
    state: WorkerState
    current_step: int
    last_action: Optional[str]
    error: Optional[str]
    artifacts_collected: List[str]
