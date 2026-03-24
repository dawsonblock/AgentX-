"""Provenance trace writer service - durable provenance tracking.

This replaces the in-memory implementation with PostgreSQL-backed storage
that persists across restarts and integrates with runtime event logging.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from runtime.runs.models import ProvenanceRecord
from runtime.events.store import EventStore


class ProvenanceService:
    """Service for managing provenance records.
    
    Provenance tracks the origin and lineage of code changes,
    including what tools were used, what inputs were provided,
    and what outputs were produced.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.event_store = EventStore(db)

    def record_step(
        self,
        run_id: UUID,
        step_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        tool_chain: Optional[List[str]] = None,
        patch_id: Optional[UUID] = None
    ) -> ProvenanceRecord:
        """Record a provenance step.
        
        Args:
            run_id: Run UUID
            step_name: Name of the step (e.g., "context_building", "patch_generation")
            input_data: Input data for the step
            output_data: Output data from the step
            tool_chain: List of tools used
            patch_id: Associated patch ID if applicable
            
        Returns:
            Created ProvenanceRecord
        """
        record = ProvenanceRecord(
            run_id=run_id,
            patch_id=patch_id,
            step_name=step_name,
            input_data=input_data,
            output_data=output_data,
            tool_chain=tool_chain or []
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        # Also emit as event for real-time monitoring
        self.event_store.append(
            run_id=run_id,
            event_type="ProvenanceRecorded",
            payload={
                "provenance_id": str(record.id),
                "step_name": step_name,
                "patch_id": str(patch_id) if patch_id else None
            }
        )
        
        return record

    def record_tool_execution(
        self,
        run_id: UUID,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Dict[str, Any],
        patch_id: Optional[UUID] = None
    ) -> ProvenanceRecord:
        """Record a tool execution for provenance.
        
        Args:
            run_id: Run UUID
            tool_name: Name of the tool executed
            tool_args: Arguments passed to the tool
            tool_result: Result from the tool
            patch_id: Associated patch ID
            
        Returns:
            Created ProvenanceRecord
        """
        return self.record_step(
            run_id=run_id,
            step_name=f"tool:{tool_name}",
            input_data={"args": tool_args},
            output_data={"result": tool_result},
            tool_chain=[tool_name],
            patch_id=patch_id
        )

    def record_context_building(
        self,
        run_id: UUID,
        task: str,
        files_selected: List[str],
        context_size: int,
        retrieval_method: str
    ) -> ProvenanceRecord:
        """Record context building step.
        
        Args:
            run_id: Run UUID
            task: The task description
            files_selected: List of files selected for context
            context_size: Size of context in tokens/bytes
            retrieval_method: Method used for retrieval
            
        Returns:
            Created ProvenanceRecord
        """
        return self.record_step(
            run_id=run_id,
            step_name="context_building",
            input_data={"task": task},
            output_data={
                "files_selected": files_selected,
                "context_size": context_size,
                "retrieval_method": retrieval_method
            }
        )

    def record_patch_generation(
        self,
        run_id: UUID,
        patch_id: UUID,
        base_commit: str,
        files_changed: List[str],
        generation_method: str
    ) -> ProvenanceRecord:
        """Record patch generation step.
        
        Args:
            run_id: Run UUID
            patch_id: Patch UUID
            base_commit: Base git commit
            files_changed: List of files changed
            generation_method: Method used to generate patch
            
        Returns:
            Created ProvenanceRecord
        """
        return self.record_step(
            run_id=run_id,
            step_name="patch_generation",
            patch_id=patch_id,
            input_data={"base_commit": base_commit},
            output_data={
                "files_changed": files_changed,
                "generation_method": generation_method
            },
            tool_chain=["worker"]
        )

    def record_approval(
        self,
        run_id: UUID,
        patch_id: UUID,
        decision: str,
        actor_id: str
    ) -> ProvenanceRecord:
        """Record approval step.
        
        Args:
            run_id: Run UUID
            patch_id: Patch UUID
            decision: 'approve' or 'reject'
            actor_id: User who made the decision
            
        Returns:
            Created ProvenanceRecord
        """
        return self.record_step(
            run_id=run_id,
            step_name=f"approval:{decision}",
            patch_id=patch_id,
            input_data={"patch_id": str(patch_id)},
            output_data={
                "decision": decision,
                "actor_id": actor_id
            },
            tool_chain=[]
        )

    def get_record(self, record_id: UUID) -> Optional[ProvenanceRecord]:
        """Get a provenance record by ID.
        
        Args:
            record_id: Provenance UUID
            
        Returns:
            ProvenanceRecord or None
        """
        return self.db.query(ProvenanceRecord).filter(ProvenanceRecord.id == record_id).first()

    def get_provenance_for_run(
        self,
        run_id: UUID,
        step_name: Optional[str] = None
    ) -> List[ProvenanceRecord]:
        """Get all provenance records for a run.
        
        Args:
            run_id: Run UUID
            step_name: Optional step name filter
            
        Returns:
            List of ProvenanceRecord objects
        """
        query = self.db.query(ProvenanceRecord).filter(ProvenanceRecord.run_id == run_id)
        
        if step_name:
            query = query.filter(ProvenanceRecord.step_name == step_name)
        
        return query.order_by(ProvenanceRecord.created_at).all()

    def get_provenance_for_patch(self, patch_id: UUID) -> List[ProvenanceRecord]:
        """Get all provenance records for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            List of ProvenanceRecord objects
        """
        return self.db.query(ProvenanceRecord)\
            .filter(ProvenanceRecord.patch_id == patch_id)\
            .order_by(ProvenanceRecord.created_at)\
            .all()

    def get_tool_chain_for_run(self, run_id: UUID) -> List[str]:
        """Get the complete tool chain used in a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            List of unique tool names
        """
        records = self.get_provenance_for_run(run_id)
        tools = set()
        
        for record in records:
            if record.tool_chain:
                tools.update(record.tool_chain)
        
        return sorted(list(tools))

    def build_lineage(self, patch_id: UUID) -> Dict[str, Any]:
        """Build a complete lineage for a patch.
        
        Args:
            patch_id: Patch UUID
            
        Returns:
            Dict with complete provenance history
        """
        records = self.get_provenance_for_patch(patch_id)
        
        return {
            "patch_id": str(patch_id),
            "steps": [
                {
                    "step_name": r.step_name,
                    "input": r.input_data,
                    "output": r.output_data,
                    "tool_chain": r.tool_chain,
                    "timestamp": r.created_at.isoformat() if r.created_at else None
                }
                for r in records
            ],
            "total_steps": len(records)
        }

    def delete_provenance_for_run(self, run_id: UUID) -> int:
        """Delete all provenance records for a run (cleanup).
        
        Args:
            run_id: Run UUID
            
        Returns:
            Number of records deleted
        """
        count = self.db.query(ProvenanceRecord).filter(ProvenanceRecord.run_id == run_id).delete()
        self.db.commit()
        return count


# Global service instance (for backward compatibility)
_service: Optional[ProvenanceService] = None


def get_service(db: Optional[Session] = None) -> ProvenanceService:
    """Get the global service instance.
    
    Args:
        db: Optional database session
        
    Returns:
        ProvenanceService instance
    """
    global _service
    if _service is None:
        if db is None:
            from ...runtime.db.session import get_db_session
            db = get_db_session()
        _service = ProvenanceService(db)
    return _service
