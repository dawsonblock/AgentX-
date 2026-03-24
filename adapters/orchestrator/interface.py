"""Orchestrator adapter interface.

Abstract interface for worktree management and patch application.
"""

from abc import ABC, abstractmethod


class Orchestrator(ABC):
    """Abstract orchestrator for worktree management."""
    
    @abstractmethod
    def prepare_worktree(self, repo_id: str, run_id: str) -> str:
        """Clone repo and prepare worktree.
        
        Args:
            repo_id: Repository URL or local path
            run_id: Run ID for naming
            
        Returns:
            Path to prepared worktree
        """
        pass
    
    @abstractmethod
    def apply_patch(self, worktree: str, patch: str) -> bool:
        """Apply patch to worktree.
        
        Args:
            worktree: Worktree path
            patch: Patch diff content
            
        Returns:
            True if successful
        """
        pass
