"""API routes for artifacts."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...artifacts.service import ArtifactService
from ...db.session import get_db

router = APIRouter()


class ArtifactResponse(BaseModel):
    """Artifact response model."""
    id: UUID
    run_id: UUID
    type: str
    filename: Optional[str]
    path: str
    size_bytes: Optional[int]
    metadata: dict
    created_at: str

    class Config:
        from_attributes = True


def get_artifact_service(db: Session = Depends(get_db)) -> ArtifactService:
    """Get artifact service with database session."""
    return ArtifactService(db)


@router.get("/run/{run_id}", response_model=dict)
def list_artifacts(
    run_id: UUID,
    type: Optional[str] = Query(None, description="Filter by artifact type"),
    service: ArtifactService = Depends(get_artifact_service)
):
    """List artifacts for a run.
    
    Args:
        run_id: Run UUID
        type: Filter by artifact kind
        service: Artifact service
        
    Returns:
        List of artifacts
    """
    artifacts = service.list_artifacts_for_run(run_id, artifact_type=type)
    return {
        "run_id": str(run_id),
        "artifacts": [a.to_dict() for a in artifacts],
        "count": len(artifacts),
        "total_size": service.get_total_size_for_run(run_id)
    }


@router.get("/{artifact_id}", response_model=dict)
def get_artifact(
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service)
):
    """Get artifact by ID.
    
    Args:
        artifact_id: Artifact UUID
        service: Artifact service
        
    Returns:
        Artifact details
    """
    artifact = service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    return artifact.to_dict()


@router.get("/{artifact_id}/content")
def get_artifact_content(
    artifact_id: UUID,
    download: bool = Query(False, description="Download as file"),
    service: ArtifactService = Depends(get_artifact_service)
):
    """Get artifact content.
    
    Args:
        artifact_id: Artifact UUID
        download: If true, return as file download
        service: Artifact service
        
    Returns:
        Artifact content (text or binary)
    """
    artifact = service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    
    content = service.get_artifact_content(artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact content not found")
    
    # Try to return as text if possible
    try:
        text_content = content.decode('utf-8')
        if download:
            return Response(
                content=text_content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename={artifact.filename or 'artifact.txt'}"
                }
            )
        return {
            "artifact_id": str(artifact_id),
            "type": artifact.type,
            "content": text_content
        }
    except UnicodeDecodeError:
        # Binary content
        if download:
            return Response(
                content=content,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename={artifact.filename or 'artifact.bin'}"
                }
            )
        return {
            "artifact_id": str(artifact_id),
            "type": artifact.type,
            "size_bytes": len(content),
            "binary": True
        }


@router.post("/run/{run_id}", response_model=dict)
def upload_artifact(
    run_id: UUID,
    type: str,
    file: UploadFile = File(...),
    metadata: Optional[str] = Query(None, description="JSON metadata"),
    service: ArtifactService = Depends(get_artifact_service)
):
    """Upload an artifact for a run.
    
    Args:
        run_id: Run UUID
        type: Artifact type
        file: File to upload
        metadata: Optional JSON metadata string
        service: Artifact service
        
    Returns:
        Created artifact
    """
    import json
    
    # Parse metadata
    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON metadata")
    
    # Read file content
    content = file.file.read()
    
    # Store artifact
    artifact = service.store_artifact(
        run_id=run_id,
        artifact_type=type,
        content=content,
        filename=file.filename or "unnamed",
        metadata=meta
    )
    
    return artifact.to_dict()


@router.delete("/{artifact_id}", response_model=dict)
def delete_artifact(
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service)
):
    """Delete an artifact.
    
    Args:
        artifact_id: Artifact UUID
        service: Artifact service
        
    Returns:
        Deletion result
    """
    success = service.delete_artifact(artifact_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    
    return {
        "artifact_id": str(artifact_id),
        "deleted": True
    }


@router.get("/run/{run_id}/total-size")
def get_total_size(
    run_id: UUID,
    service: ArtifactService = Depends(get_artifact_service)
):
    """Get total artifact size for a run.
    
    Args:
        run_id: Run UUID
        service: Artifact service
        
    Returns:
        Total size in bytes
    """
    total = service.get_total_size_for_run(run_id)
    return {
        "run_id": str(run_id),
        "total_size_bytes": total,
        "total_size_mb": round(total / (1024 * 1024), 2) if total else 0
    }
