"""Worker adapter interface.

Abstract interface for code generation workers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class Worker(ABC):
    """Abstract worker for code generation."""
    
    @abstractmethod
    def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task and return result.
        
        Args:
            task: Task description
            context: Context with files and metadata
            
        Returns:
            Result with patch, logs, and artifacts
        """
        pass
