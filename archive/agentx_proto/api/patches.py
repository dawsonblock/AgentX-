"""Patch API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from services.patch_service import PatchService

router = APIRouter()


@router.get("/{patch_id}")
def get_patch(patch_id: str, db: Session = Depends(get_db)):
    """Get patch details."""
    patch = PatchService(db).get(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    return {
        "id": patch.id,
        "run_id": patch.run_id,
        "status": patch.status,
        "summary": patch.summary,
        "diff": patch.diff,
        "created_at": patch.created_at
    }


@router.get("/run/{run_id}")
def list_patches(run_id: str, db: Session = Depends(get_db)):
    """List patches for a run."""
    patches = PatchService(db).list_for_run(run_id)
    return [
        {
            "id": p.id,
            "status": p.status,
            "summary": p.summary,
            "created_at": p.created_at
        }
        for p in patches
    ]
