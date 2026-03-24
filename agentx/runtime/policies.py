"""Runtime policies and constraints."""

from core.errors import PolicyDenied
from core.logging import get_logger

logger = get_logger(__name__)


# Allowed tools for worker
ALLOWED_TOOLS = {"read_file", "search", "run_tests", "git_diff"}

# Maximum values
MAX_STEPS = 20
MAX_FILES_TOUCHED = 50
MAX_OUTPUT_SIZE = 100000  # characters


def check_tool(name: str) -> None:
    """Check if a tool is allowed.
    
    Args:
        name: Tool name
        
    Raises:
        PolicyDenied: If tool is not in allowlist
    """
    if name not in ALLOWED_TOOLS:
        logger.error(f"Tool not allowed: {name}")
        raise PolicyDenied(f"Tool not allowed: {name}")


def check_steps(current_step: int) -> None:
    """Check if step limit is exceeded.
    
    Args:
        current_step: Current step number
        
    Raises:
        PolicyDenied: If step limit exceeded
    """
    if current_step >= MAX_STEPS:
        logger.error(f"Max steps ({MAX_STEPS}) exceeded")
        raise PolicyDenied(f"Max steps ({MAX_STEPS}) exceeded")


def check_files_touched(count: int) -> None:
    """Check if files touched limit is exceeded.
    
    Args:
        count: Number of files touched
        
    Raises:
        PolicyDenied: If limit exceeded
    """
    if count >= MAX_FILES_TOUCHED:
        logger.error(f"Max files touched ({MAX_FILES_TOUCHED}) exceeded")
        raise PolicyDenied(f"Max files touched ({MAX_FILES_TOUCHED}) exceeded")


def sanitize_path(path: str, worktree: str) -> str:
    """Sanitize a path to ensure it's within the worktree.
    
    Args:
        path: User-provided path
        worktree: Worktree root path
        
    Returns:
        Sanitized absolute path
        
    Raises:
        PolicyDenied: If path escapes worktree
    """
    import os
    
    # Normalize path
    if not os.path.isabs(path):
        path = os.path.join(worktree, path)
    
    path = os.path.normpath(os.path.abspath(path))
    worktree = os.path.normpath(os.path.abspath(worktree))
    
    # Check if path is within worktree
    if not path.startswith(worktree):
        logger.error(f"Path escape attempt: {path}")
        raise PolicyDenied(f"Path {path} is outside worktree")
    
    return path
