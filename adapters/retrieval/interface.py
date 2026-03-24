"""Retrieval adapter interface.

Abstract interface for context building.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class Retrieval(ABC):
    """Abstract retrieval for context building."""
    
    @abstractmethod
    def build_context(self, repo_path: str, task: str) -> Dict[str, Any]:
        """Build context for task.
        
        Args:
            repo_path: Repository path
            task: Task description
            
        Returns:
            Context dictionary with files and metadata
        """
        pass
