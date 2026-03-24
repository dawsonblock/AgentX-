"""Worktree allocation and management."""

import os
import shutil
import uuid
import subprocess
from typing import Optional

from core.config import Settings
from core.logging import get_logger

logger = get_logger(__name__)


def allocate(repo_url: str) -> str:
    """Allocate a new worktree for a repository.
    
    Args:
        repo_url: Repository URL or local path
        
    Returns:
        Path to allocated worktree
    """
    os.makedirs(Settings.WORKTREE_ROOT, exist_ok=True)
    
    worktree_id = str(uuid.uuid4())
    path = os.path.join(Settings.WORKTREE_ROOT, worktree_id)
    
    logger.info(f"Allocating worktree {worktree_id} for {repo_url}")
    
    if os.path.exists(repo_url):
        # Local repo - clone it
        subprocess.run(["git", "clone", repo_url, path], check=True, capture_output=True)
    else:
        # Remote repo
        subprocess.run(["git", "clone", repo_url, path], check=True, capture_output=True)
    
    logger.info(f"Worktree allocated at {path}")
    return path


def cleanup(path: str) -> None:
    """Clean up a worktree.
    
    Args:
        path: Worktree path to remove
    """
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
        logger.info(f"Cleaned up worktree {path}")


def get_git_commit(path: str) -> Optional[str]:
    """Get current git commit hash.
    
    Args:
        path: Repository path
        
    Returns:
        Commit hash or None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return None
