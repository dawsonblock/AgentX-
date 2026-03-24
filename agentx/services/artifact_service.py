"""Artifact service - business logic for artifacts."""

import os
from typing import Optional, List
from sqlalchemy.orm import Session

from db.models import Artifact
from core.logging import get_logger

logger = get_logger(__name__)


class ArtifactService:
    """Service for managing artifacts."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def store(
        self,
        run_id: str,
        path: str,
        artifact_type: str,
        meta: Optional[dict] = None
    ) -> Artifact:
        """Store an artifact.
        
        Args:
            run_id: Parent run ID
            path: File path
            artifact_type: Type of artifact (log, test, etc.)
            meta: Optional metadata
            
        Returns:
            Created Artifact instance
        """
        size = None
        if os.path.exists(path):
            size = os.path.getsize(path)
        
        artifact = Artifact(
            run_id=run_id,
            path=path,
            type=artifact_type,
            meta=meta or {},
            size_bytes=size
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        logger.info(f"Stored artifact {artifact.id} ({artifact_type})")
        return artifact
    
    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get an artifact by ID."""
        return self.db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    def list_for_run(self, run_id: str) -> List[Artifact]:
        """List all artifacts for a run."""
        return self.db.query(Artifact).filter(Artifact.run_id == run_id).order_by(Artifact.created_at.desc()).all()
