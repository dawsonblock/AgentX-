"""Artifact API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from services.artifact_service import ArtifactService

router = APIRouter()


@router.get("/run/{run_id}")
def list_artifacts(run_id: str, db: Session = Depends(get_db)):
    """List artifacts for a run."""
    artifacts = ArtifactService(db).list_for_run(run_id)
    return [
        {
            "id": a.id,
            "type": a.type,
            "path": a.path,
            "size": a.size_bytes,
            "meta": a.meta,
            "created_at": a.created_at
        }
        for a in artifacts
    ]


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    """Get artifact details."""
    artifact = ArtifactService(db).get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {
        "id": artifact.id,
        "run_id": artifact.run_id,
        "type": artifact.type,
        "path": artifact.path,
        "size": artifact.size_bytes,
        "meta": artifact.meta,
        "created_at": artifact.created_at
    }
