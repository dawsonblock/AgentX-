"""GSD Wrapper module.

Wraps the GSD worker with runtime-mediated tool access.
"""

from .service import GSDWrapper
from .contracts import (
    WorkerState,
    WorkerAction,
    TaskSpec,
    WorkerStatus,
    WorkerStepResult,
    PatchProposal
)
from .tool_bridge import ToolBridge

__all__ = [
    "GSDWrapper",
    "WorkerState",
    "WorkerAction",
    "TaskSpec",
    "WorkerStatus",
    "WorkerStepResult",
    "PatchProposal",
    "ToolBridge",
]
