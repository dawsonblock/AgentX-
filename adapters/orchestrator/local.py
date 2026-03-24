"""Local orchestrator implementation.

Git-based orchestrator for local development.
"""

import os
import subprocess
import logging
from typing import Optional

from .interface import Orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalOrchestrator(Orchestrator):
    """Local git-based orchestrator."""
    
    def __init__(self, worktree_root: Optional[str] = None):
        self.worktree_root = worktree_root or os.getenv(
            "WORKTREE_ROOT", 
            "/var/lib/agentx/worktrees"
        )
        os.makedirs(self.worktree_root, exist_ok=True)
    
    def prepare_worktree(self, repo_id: str, run_id: str) -> str:
        """Clone repo and prepare worktree."""
        path = os.path.join(self.worktree_root, run_id)
        
        if os.path.exists(path):
            logger.warning(f"Worktree {path} exists, removing")
            import shutil
            shutil.rmtree(path)
        
        logger.info(f"Cloning {repo_id} to {path}")
        
        # Clone repository
        subprocess.run(
            ["git", "clone", repo_id, path],
            check=True,
            capture_output=True,
            timeout=120
        )
        
        # Create branch
        branch_name = f"agentx/run-{run_id[:8]}"
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=path,
            check=True,
            capture_output=True
        )
        
        logger.info(f"Worktree ready at {path} on branch {branch_name}")
        return path
    
    def apply_patch(self, worktree: str, patch: str) -> bool:
        """Apply patch to worktree."""
        patch_file = os.path.join(worktree, ".agentx-patch.diff")
        
        try:
            # Write patch to file
            with open(patch_file, "w") as f:
                f.write(patch)
            
            # Apply patch
            result = subprocess.run(
                ["git", "apply", patch_file],
                cwd=worktree,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Patch applied successfully to {worktree}")
                return True
            else:
                logger.error(f"Patch apply failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Patch apply error: {e}")
            return False
        finally:
            # Cleanup
            if os.path.exists(patch_file):
                os.unlink(patch_file)
