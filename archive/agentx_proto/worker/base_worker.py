"""Base worker interface."""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class WorkerResult:
    """Result of worker execution."""
    diff: str
    summary: str = ""
    files_modified: int = 0
    notes: List[str] = None
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []


class BaseWorker:
    """Base class for workers."""
    
    def execute(self, task: str, context: List[Dict[str, Any]], worktree: str) -> WorkerResult:
        """Execute the worker.
        
        Args:
            task: Task description
            context: Context files
            worktree: Worktree path
            
        Returns:
            WorkerResult with diff
        """
        raise NotImplementedError
