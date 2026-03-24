"""API routes for CI checks."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...ci.service import get_service as get_ci_service, CIResult, CIGateStatus
from ...runs.models import CICheck
from ...db.session import get_db

router = APIRouter()


class CIGateResponse(BaseModel):
    """CI gate response."""
    name: str
    status: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class CIResultResponse(BaseModel):
    """CI result response."""
    patch_id: str
    overall_status: str
    gates: List[CIGateResponse]
    summary: str


class CICheckResponse(BaseModel):
    """CI check database record response."""
    id: UUID
    patch_id: UUID
    run_id: UUID
    gate_name: str
    status: str
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    duration_ms: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


def get_ci_service():
    """Get CI service."""
    return get_ci_service()


@router.get("/patch/{patch_id}", response_model=dict)
def get_ci_checks_for_patch(
    patch_id: UUID,
    db: Session = Depends(get_db)
):
    """Get CI checks for a patch.
    
    Args:
        patch_id: Patch UUID
        db: Database session
        
    Returns:
        List of CI checks
    """
    checks = db.query(CICheck).filter(CICheck.patch_id == patch_id).order_by(CICheck.created_at.asc()).all()
    
    return {
        "patch_id": str(patch_id),
        "checks": [check.to_dict() for check in checks],
        "count": len(checks)
    }


@router.get("/patch/{patch_id}/summary", response_model=dict)
def get_ci_summary_for_patch(
    patch_id: UUID,
    db: Session = Depends(get_db)
):
    """Get CI summary for a patch.
    
    Args:
        patch_id: Patch UUID
        db: Database session
        
    Returns:
        CI summary
    """
    checks = db.query(CICheck).filter(CICheck.patch_id == patch_id).all()
    
    if not checks:
        return {
            "patch_id": str(patch_id),
            "status": "not_run",
            "summary": "No CI checks have been run"
        }
    
    passed = sum(1 for c in checks if c.status == 'passed')
    failed = sum(1 for c in checks if c.status == 'failed')
    skipped = sum(1 for c in checks if c.status == 'skipped')
    
    total_duration = sum(c.duration_ms or 0 for c in checks)
    
    if failed > 0:
        overall_status = 'failed'
    elif skipped == len(checks):
        overall_status = 'skipped'
    else:
        overall_status = 'passed'
    
    return {
        "patch_id": str(patch_id),
        "status": overall_status,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total_duration_ms": total_duration,
        "summary": f"{passed} passed, {failed} failed, {skipped} skipped"
    }


@router.post("/run/{run_id}/patch/{patch_id}", response_model=dict)
def run_ci_checks(
    run_id: UUID,
    patch_id: UUID,
    gates: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Manually trigger CI checks for a patch.
    
    Note: CI is automatically run on approval. This endpoint is for manual runs.
    
    Args:
        run_id: Run UUID
        patch_id: Patch UUID
        gates: Optional list of gates to run
        db: Database session
        
    Returns:
        CI result
    """
    from ...runs.models import Worktree
    
    # Get worktree
    worktree = db.query(Worktree).filter(Worktree.run_id == run_id).first()
    if not worktree:
        raise HTTPException(status_code=404, detail="Worktree not found")
    
    # Run CI
    ci_service = get_ci_service()
    repo_type = ci_service.detect_repo_type(worktree.path)
    
    ci_result = ci_service.run_ci_checks(
        worktree_path=worktree.path,
        patch_id=str(patch_id),
        gates=gates or ci_service.DEFAULT_GATES,
        repo_type=repo_type
    )
    
    # Store results
    for gate in ci_result.gates:
        check = CICheck(
            patch_id=patch_id,
            run_id=run_id,
            gate_name=gate.name,
            status=gate.status.value,
            exit_code=gate.exit_code,
            stdout=gate.stdout,
            stderr=gate.stderr,
            duration_ms=gate.duration_ms
        )
        db.add(check)
    
    db.commit()
    
    return {
        "patch_id": str(patch_id),
        "overall_status": ci_result.overall_status.value,
        "summary": ci_result.summary,
        "gates": [
            {
                "name": g.name,
                "status": g.status.value,
                "exit_code": g.exit_code,
                "duration_ms": g.duration_ms
            }
            for g in ci_result.gates
        ]
    }


@router.get("/run/{run_id}", response_model=dict)
def get_ci_checks_for_run(
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all CI checks for a run.
    
    Args:
        run_id: Run UUID
        db: Database session
        
    Returns:
        List of CI checks grouped by patch
    """
    checks = db.query(CICheck).filter(CICheck.run_id == run_id).order_by(CICheck.created_at.asc()).all()
    
    # Group by patch
    by_patch = {}
    for check in checks:
        patch_id = str(check.patch_id)
        if patch_id not in by_patch:
            by_patch[patch_id] = []
        by_patch[patch_id].append(check.to_dict())
    
    return {
        "run_id": str(run_id),
        "checks_by_patch": by_patch,
        "total_checks": len(checks)
    }
