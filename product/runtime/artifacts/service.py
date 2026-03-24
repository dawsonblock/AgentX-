"""Artifact service - business logic for artifact management."""

import os
import shutil
from uuid import UUID
from typing import Optional, List, BinaryIO
from sqlalchemy.orm import Session

from ..runs.models import Artifact
from ..events.store import EventStore

# Artifact storage root
ARTIFACT_ROOT = os.environ.get("ARTIFACT_ROOT", "/var/lib/product/artifacts")


class ArtifactService:
    """Service for managing artifacts.
    
    Handles artifact storage, retrieval, and cleanup.
    Artifacts are stored on filesystem with metadata in PostgreSQL.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.event_store = EventStore(db)
        self._ensure_root_exists()

    def _ensure_root_exists(self):
        """Ensure artifact root directory exists."""
        if not os.path.exists(ARTIFACT_ROOT):
            os.makedirs(ARTIFACT_ROOT, exist_ok=True)

    def _get_run_directory(self, run_id: UUID) -> str:
        """Get the directory path for a run's artifacts."""
        return os.path.join(ARTIFACT_ROOT, str(run_id))

    def _get_artifact_path(self, run_id: UUID, artifact_id: UUID, filename: str) -> str:
        """Get the full path for an artifact file."""
        run_dir = self._get_run_directory(run_id)
        return os.path.join(run_dir, f"{artifact_id}-{filename}")

    def store_artifact(
        self,
        run_id: UUID,
        artifact_type: str,
        content: bytes,
        filename: str,
        metadata: Optional[dict] = None
    ) -> Artifact:
        """Store an artifact.
        
        Args:
            run_id: Run UUID
            artifact_type: Type of artifact (log, test, patch, report, context)
            content: Binary content of the artifact
            filename: Original filename
            metadata: Optional metadata dict
            
        Returns:
            Created Artifact object
        """
        # Ensure run directory exists
        run_dir = self._get_run_directory(run_id)
        os.makedirs(run_dir, exist_ok=True)
        
        # Create artifact record
        artifact = Artifact(
            run_id=run_id,
            type=artifact_type,
            filename=filename,
            path="",  # Will update after we know the ID
            size_bytes=len(content),
            metadata_json=metadata or {}
        )
        
        self.db.add(artifact)
        self.db.flush()  # Get the ID
        
        # Write content to filesystem
        artifact_path = self._get_artifact_path(run_id, artifact.id, filename)
        with open(artifact_path, 'wb') as f:
            f.write(content)
        
        # Update path in record
        artifact.path = artifact_path
        self.db.commit()
        self.db.refresh(artifact)
        
        # Emit event
        self.event_store.append(
            run_id=run_id,
            event_type="ArtifactStored",
            payload={
                "artifact_id": str(artifact.id),
                "type": artifact_type,
                "filename": filename,
                "size_bytes": len(content)
            }
        )
        
        return artifact

    def store_artifact_from_file(
        self,
        run_id: UUID,
        artifact_type: str,
        source_path: str,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Artifact:
        """Store an artifact from a file path.
        
        Args:
            run_id: Run UUID
            artifact_type: Type of artifact
            source_path: Path to source file
            filename: Optional filename override
            metadata: Optional metadata dict
            
        Returns:
            Created Artifact object
        """
        if filename is None:
            filename = os.path.basename(source_path)
        
        with open(source_path, 'rb') as f:
            content = f.read()
        
        return self.store_artifact(run_id, artifact_type, content, filename, metadata)

    def get_artifact(self, artifact_id: UUID) -> Optional[Artifact]:
        """Get artifact by ID.
        
        Args:
            artifact_id: Artifact UUID
            
        Returns:
            Artifact object or None
        """
        return self.db.query(Artifact).filter(Artifact.id == artifact_id).first()

    def list_artifacts_for_run(
        self,
        run_id: UUID,
        artifact_type: Optional[str] = None
    ) -> List[Artifact]:
        """List artifacts for a run.
        
        Args:
            run_id: Run UUID
            artifact_type: Optional type filter
            
        Returns:
            List of Artifact objects
        """
        query = self.db.query(Artifact).filter(Artifact.run_id == run_id)
        
        if artifact_type:
            query = query.filter(Artifact.type == artifact_type)
        
        return query.order_by(Artifact.created_at.desc()).all()

    def get_artifact_content(self, artifact_id: UUID) -> Optional[bytes]:
        """Get the binary content of an artifact.
        
        Args:
            artifact_id: Artifact UUID
            
        Returns:
            Content bytes or None if not found
        """
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            return None
        
        try:
            with open(artifact.path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def get_artifact_text(self, artifact_id: UUID, encoding: str = 'utf-8') -> Optional[str]:
        """Get the text content of an artifact.
        
        Args:
            artifact_id: Artifact UUID
            encoding: Text encoding
            
        Returns:
            Content string or None if not found/binary
        """
        content = self.get_artifact_content(artifact_id)
        if content is None:
            return None
        
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            return None

    def delete_artifact(self, artifact_id: UUID) -> bool:
        """Delete an artifact.
        
        Args:
            artifact_id: Artifact UUID
            
        Returns:
            True if deleted, False if not found
        """
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            return False
        
        # Delete from filesystem
        try:
            if os.path.exists(artifact.path):
                os.remove(artifact.path)
        except Exception:
            pass  # Continue even if file delete fails
        
        # Delete from database
        self.db.delete(artifact)
        self.db.commit()
        
        return True

    def delete_artifacts_for_run(self, run_id: UUID) -> int:
        """Delete all artifacts for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Number of artifacts deleted
        """
        artifacts = self.list_artifacts_for_run(run_id)
        count = 0
        
        for artifact in artifacts:
            if self.delete_artifact(artifact.id):
                count += 1
        
        # Clean up run directory
        run_dir = self._get_run_directory(run_id)
        try:
            if os.path.exists(run_dir):
                shutil.rmtree(run_dir)
        except Exception:
            pass
        
        return count

    def get_total_size_for_run(self, run_id: UUID) -> int:
        """Get total size of all artifacts for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Total size in bytes
        """
        artifacts = self.list_artifacts_for_run(run_id)
        return sum(a.size_bytes or 0 for a in artifacts)

    def artifact_exists(self, artifact_id: UUID) -> bool:
        """Check if an artifact exists and is accessible.
        
        Args:
            artifact_id: Artifact UUID
            
        Returns:
            True if exists, False otherwise
        """
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            return False
        
        return os.path.exists(artifact.path)
