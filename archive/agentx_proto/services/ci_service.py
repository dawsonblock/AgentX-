"""CI service - runs quality checks on patches."""

import subprocess
from typing import Optional
from core.logging import get_logger

logger = get_logger(__name__)


class CIService:
    """Service for running CI checks."""
    
    def run(self, worktree: str, command: Optional[list] = None) -> bool:
        """Run CI checks in a worktree.
        
        Args:
            worktree: Path to worktree
            command: Optional custom command (default: pytest)
            
        Returns:
            True if checks pass, False otherwise
        """
        cmd = command or ["pytest"]
        logger.info(f"Running CI in {worktree}: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=300
            )
            passed = result.returncode == 0
            if passed:
                logger.info(f"CI passed in {worktree}")
            else:
                logger.warning(f"CI failed in {worktree}: {result.stderr[:500]}")
            return passed
        except subprocess.TimeoutExpired:
            logger.error(f"CI timed out in {worktree}")
            return False
        except Exception as e:
            logger.error(f"CI error in {worktree}: {e}")
            return False
    
    def run_lint(self, worktree: str) -> bool:
        """Run linting checks."""
        return self.run(worktree, ["flake8"])
    
    def run_typecheck(self, worktree: str) -> bool:
        """Run type checking."""
        return self.run(worktree, ["mypy", "."])
