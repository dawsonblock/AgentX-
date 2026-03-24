"""Patch service - business logic for patch lifecycle."""

import subprocess
from uuid import UUID
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..runs.models import Patch
from ..events.store import EventStore


class PatchService:
    """Service for managing patches.
    
    Handles patch creation, retrieval, status updates, and application.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.event_store = EventStore(db)

    def create_patch(
        self,
        run_id: UUID,
        worktree_id: str,
        base_commit: str,
        diff_text: str,
        summary: Optional[str] = None
    ) -> Patch:
        """Create a new patch.
        
        Args:
            run_id: Run UUID
            worktree_id: Worktree identifier
            base_commit: Base git commit SHA
            diff_text: The unified diff text
            summary: Optional human-readable summary
            
        Returns:
            Created Patch object
        """
        # Generate summary from diff if not provided
        if not summary:
            summary = self._generate_summary(diff_text)
        
        patch = Patch(
            run_id=run_id,
            worktree_id=worktree_id,
            base_commit=base_commit,
            diff_text=diff_text,
            summary=summary,
            status="proposed"
        )
        
        self.db.add(patch)
        self.db.commit()
        self.db.refresh(patch)
        
        # Emit patch created event
        self.event_store.append(
            run_id=run_id,
            event_type="PatchCreated",
            payload={
                "patch_id": str(patch.id),
                "base_commit": base_commit,
                "summary": summary
            }
        )
        
        return patch

    def get_patch(self, patch_id: UUID) -> Optional[Patch]:
        """Get patch by ID.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            Patch object or None
        """
        return self.db.query(Patch).filter(Patch.id == patch_id).first()

    def list_patches_for_run(self, run_id: UUID) -> List[Patch]:
        """List all patches for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            List of Patch objects
        """
        return self.db.query(Patch).filter(Patch.run_id == run_id).order_by(Patch.created_at.desc()).all()

    def update_status(self, patch_id: UUID, status: str) -> Optional[Patch]:
        """Update patch status.
        
        Args:
            patch_id: Patch UUID
            status: New status (proposed | approved | rejected | applied)
            
        Returns:
            Updated Patch object or None
        """
        patch = self.get_patch(patch_id)
        if not patch:
            return None
        
        old_status = patch.status
        patch.status = status
        self.db.commit()
        
        # Emit status change event
        self.event_store.append(
            run_id=patch.run_id,
            event_type="PatchStatusChanged",
            payload={
                "patch_id": str(patch_id),
                "old_status": old_status,
                "new_status": status
            }
        )
        
        return patch

    def apply_patch_to_worktree(self, patch_id: UUID, worktree_path: str) -> bool:
        """Apply a patch to a worktree using git apply.
        
        Args:
            patch_id: Patch UUID
            worktree_path: Path to the worktree
            
        Returns:
            True if applied successfully, False otherwise
        """
        patch = self.get_patch(patch_id)
        if not patch:
            return False
        
        try:
            # Apply the patch using git apply
            result = subprocess.run(
                ["git", "apply", "-"],
                input=patch.diff_text.encode(),
                cwd=worktree_path,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Update status to applied
                self.update_status(patch_id, "applied")
                
                # Emit event
                self.event_store.append(
                    run_id=patch.run_id,
                    event_type="PatchApplied",
                    payload={
                        "patch_id": str(patch_id),
                        "worktree_path": worktree_path
                    }
                )
                return True
            else:
                # Application failed
                self.event_store.append(
                    run_id=patch.run_id,
                    event_type="PatchApplyFailed",
                    payload={
                        "patch_id": str(patch_id),
                        "error": result.stderr.decode()[:500]
                    }
                )
                return False
                
        except Exception as e:
            self.event_store.append(
                run_id=patch.run_id,
                event_type="PatchApplyFailed",
                payload={
                    "patch_id": str(patch_id),
                    "error": str(e)
                }
            )
            return False

    def _generate_summary(self, diff_text: str) -> str:
        """Generate a summary from diff text.
        
        Args:
            diff_text: The unified diff
            
        Returns:
            Summary string
        """
        lines = diff_text.split('\n')
        
        # Count file changes
        files_changed = 0
        insertions = 0
        deletions = 0
        
        for line in lines:
            if line.startswith('diff --git'):
                files_changed += 1
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        return f"Changes: {files_changed} files, +{insertions}/-{deletions} lines"

    def get_patch_stats(self, patch_id: UUID) -> Optional[Dict[str, Any]]:
        """Get statistics for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            Stats dict or None
        """
        patch = self.get_patch(patch_id)
        if not patch:
            return None
        
        diff_text = patch.diff_text or ""
        lines = diff_text.split('\n')
        
        files = []
        insertions = 0
        deletions = 0
        current_file = None
        
        for line in lines:
            if line.startswith('diff --git'):
                # Extract filename from "diff --git a/path b/path"
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[2][2:]  # Remove "a/" prefix
                    files.append(current_file)
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        return {
            "files_changed": len(files),
            "files": files,
            "insertions": insertions,
            "deletions": deletions,
            "total_lines_changed": insertions + deletions
        }
