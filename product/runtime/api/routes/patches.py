"""API routes for patches."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Body, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...patches.service import PatchService
from ...runs.models import Patch
from ...db.session import get_db

router = APIRouter()


class PatchCreateRequest(BaseModel):
    """Request to create a patch."""
    run_id: UUID
    worktree_id: str
    base_commit: str
    diff_text: str
    summary: Optional[str] = None


class PatchResponse(BaseModel):
    """Patch response model."""
    id: UUID
    run_id: UUID
    worktree_id: str
    base_commit: str
    diff_text: str
    summary: Optional[str]
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PatchStatsResponse(BaseModel):
    """Patch statistics response."""
    files_changed: int
    files: List[str]
    insertions: int
    deletions: int
    total_lines_changed: int


def get_patch_service(db: Session = Depends(get_db)) -> PatchService:
    """Get patch service with database session."""
    return PatchService(db)


@router.get("/run/{run_id}", response_model=dict)
def get_run_patches(
    run_id: UUID,
    service: PatchService = Depends(get_patch_service)
):
    """Get patches for a run.
    
    Args:
        run_id: Run UUID
        service: Patch service
        
    Returns:
        List of patches
    """
    patches = service.list_patches_for_run(run_id)
    return {
        "run_id": str(run_id),
        "patches": [p.to_dict() for p in patches],
        "count": len(patches)
    }


@router.get("/{patch_id}", response_model=dict)
def get_patch(
    patch_id: UUID,
    service: PatchService = Depends(get_patch_service)
):
    """Get patch by ID.
    
    Args:
        patch_id: Patch UUID
        service: Patch service
        
    Returns:
        Patch details
    """
    patch = service.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    return patch.to_dict()


@router.get("/{patch_id}/diff")
def get_patch_diff(
    patch_id: UUID,
    service: PatchService = Depends(get_patch_service)
):
    """Get patch diff text.
    
    Args:
        patch_id: Patch UUID
        service: Patch service
        
    Returns:
        Raw diff text
    """
    patch = service.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    
    return {
        "patch_id": str(patch_id),
        "diff": patch.diff_text
    }


@router.get("/{patch_id}/stats", response_model=PatchStatsResponse)
def get_patch_stats(
    patch_id: UUID,
    service: PatchService = Depends(get_patch_service)
):
    """Get patch statistics.
    
    Args:
        patch_id: Patch UUID
        service: Patch service
        
    Returns:
        Patch statistics
    """
    stats = service.get_patch_stats(patch_id)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    return PatchStatsResponse(**stats)


@router.post("/run/{run_id}", response_model=dict)
def create_patch(
    run_id: UUID,
    req: PatchCreateRequest,
    service: PatchService = Depends(get_patch_service)
):
    """Create a patch for a run.
    
    Args:
        run_id: Run UUID
        req: Patch creation request
        service: Patch service
        
    Returns:
        Created patch
    """
    patch = service.create_patch(
        run_id=req.run_id,
        worktree_id=req.worktree_id,
        base_commit=req.base_commit,
        diff_text=req.diff_text,
        summary=req.summary
    )
    return patch.to_dict()


@router.post("/{patch_id}/apply", response_model=dict)
def apply_patch(
    patch_id: UUID,
    worktree_path: Optional[str] = Body(None),
    service: PatchService = Depends(get_patch_service),
    db: Session = Depends(get_db)
):
    """Apply a patch to a worktree.
    
    Note: This is typically called internally by the executor after approval.
    
    Args:
        patch_id: Patch UUID
        worktree_path: Path to worktree (if not stored in patch)
        service: Patch service
        db: Database session
        
    Returns:
        Application result
    """
    patch = service.get_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    
    # Get worktree path
    if not worktree_path:
        worktree_path = patch.worktree_id  # This is actually the worktree ID, need to look up
        # Get actual path from worktree record
        from ...runs.models import Worktree
        worktree = db.query(Worktree).filter(Worktree.id == UUID(patch.worktree_id)).first() if patch.worktree_id else None
        if worktree:
            worktree_path = worktree.path
        else:
            raise HTTPException(status_code=400, detail="Worktree path not available")
    
    success = service.apply_patch_to_worktree(patch_id, worktree_path)
    
    if success:
        return {
            "patch_id": str(patch_id),
            "status": "applied",
            "worktree_path": worktree_path
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to apply patch")


@router.post("/{patch_id}/status", response_model=dict)
def update_patch_status(
    patch_id: UUID,
    status: str = Body(..., embed=True),
    service: PatchService = Depends(get_patch_service)
):
    """Update patch status.
    
    Args:
        patch_id: Patch UUID
        status: New status (proposed | approved | rejected | applied)
        service: Patch service
        
    Returns:
        Updated patch
    """
    if status not in ("proposed", "approved", "rejected", "applied"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    patch = service.update_status(patch_id, status)
    if not patch:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
    
    return patch.to_dict()
