"""Provenance Trace Writer Service

Records provenance metadata for patches and artifacts.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ProvenanceRecord:
    """A provenance record for a patch or artifact."""
    id: str
    run_id: str
    patch_id: Optional[str]
    file_path: str
    line_ranges: List[Dict[str, int]]
    worker_profile: str
    model_id: str
    tool_chain: List[str]
    approval_state: str
    commit_sha: Optional[str]
    created_at: datetime


class ProvenanceService:
    """Service for managing provenance records."""

    def __init__(self):
        """Initialize the service."""
        # In production, this would connect to a database
        self._records: Dict[str, ProvenanceRecord] = {}

    def write_trace(
        self,
        run_id: str,
        patch_id: Optional[str],
        file_path: str,
        line_ranges: List[Dict[str, int]],
        worker_profile: str,
        model_id: str,
        tool_chain: List[str],
        approval_state: str,
        commit_sha: Optional[str] = None
    ) -> ProvenanceRecord:
        """Write a provenance record.
        
        Args:
            run_id: Run ID
            patch_id: Patch ID
            file_path: File path
            line_ranges: Changed line ranges
            worker_profile: Worker profile used
            model_id: Model identifier
            tool_chain: Tools used in generation
            approval_state: Current approval state
            commit_sha: Git commit SHA if promoted
            
        Returns:
            Created provenance record
        """
        record = ProvenanceRecord(
            id=str(uuid4()),
            run_id=run_id,
            patch_id=patch_id,
            file_path=file_path,
            line_ranges=line_ranges,
            worker_profile=worker_profile,
            model_id=model_id,
            tool_chain=tool_chain,
            approval_state=approval_state,
            commit_sha=commit_sha,
            created_at=datetime.utcnow()
        )
        
        self._records[record.id] = record
        
        return record

    def get_records_for_run(self, run_id: str) -> List[ProvenanceRecord]:
        """Get all provenance records for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of provenance records
        """
        return [
            r for r in self._records.values()
            if r.run_id == run_id
        ]

    def get_records_for_patch(self, patch_id: str) -> List[ProvenanceRecord]:
        """Get all provenance records for a patch.
        
        Args:
            patch_id: Patch ID
            
        Returns:
            List of provenance records
        """
        return [
            r for r in self._records.values()
            if r.patch_id == patch_id
        ]

    def update_approval_state(
        self,
        record_id: str,
        approval_state: str
    ) -> Optional[ProvenanceRecord]:
        """Update the approval state of a record.
        
        Args:
            record_id: Record ID
            approval_state: New approval state
            
        Returns:
            Updated record or None
        """
        record = self._records.get(record_id)
        if record:
            record.approval_state = approval_state
        return record

    def update_commit_sha(
        self,
        record_id: str,
        commit_sha: str
    ) -> Optional[ProvenanceRecord]:
        """Update the commit SHA of a record.
        
        Args:
            record_id: Record ID
            commit_sha: Git commit SHA
            
        Returns:
            Updated record or None
        """
        record = self._records.get(record_id)
        if record:
            record.commit_sha = commit_sha
        return record

    def to_dict(self, record: ProvenanceRecord) -> Dict[str, Any]:
        """Convert record to dictionary.
        
        Args:
            record: Provenance record
            
        Returns:
            Dictionary representation
        """
        return {
            "id": record.id,
            "run_id": record.run_id,
            "patch_id": record.patch_id,
            "file_path": record.file_path,
            "line_ranges": record.line_ranges,
            "worker_profile": record.worker_profile,
            "model_id": record.model_id,
            "tool_chain": record.tool_chain,
            "approval_state": record.approval_state,
            "commit_sha": record.commit_sha,
            "created_at": record.created_at.isoformat()
        }


# Global service instance
_service: Optional[ProvenanceService] = None


def get_service() -> ProvenanceService:
    """Get the global service instance.
    
    Returns:
        ProvenanceService instance
    """
    global _service
    if _service is None:
        _service = ProvenanceService()
    return _service
