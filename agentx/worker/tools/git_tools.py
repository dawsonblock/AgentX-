"""Git tools."""

import subprocess
from core.logging import get_logger

logger = get_logger(__name__)


def git_diff(root: str) -> str:
    """Get git diff.
    
    Args:
        root: Repository root
        
    Returns:
        Diff content
    """
    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"git diff failed: {e}")
        return ""


def apply_patch(root: str, diff: str) -> bool:
    """Apply a patch.
    
    Args:
        root: Repository root
        diff: Diff content
        
    Returns:
        True if successful
    """
    try:
        proc = subprocess.Popen(
            ["git", "apply", "-"],
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        proc.communicate(input=diff)
        return proc.returncode == 0
    except Exception as e:
        logger.error(f"apply patch failed: {e}")
        return False


def git_status(root: str) -> str:
    """Get git status.
    
    Args:
        root: Repository root
        
    Returns:
        Status output
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""
