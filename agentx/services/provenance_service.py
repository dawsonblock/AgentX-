"""Provenance service - traceability records."""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from db.models import Provenance
from core.logging import get_logger

logger = get_logger(__name__)


class ProvenanceService:
    """Service for managing provenance records."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def record(
        self,
        run_id: str,
        step: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None
    ) -> Provenance:
        """Record a provenance step.
        
        Args:
            run_id: Parent run ID
            step: Step name
            input_data: Optional input data
            output_data: Optional output data
            
        Returns:
            Created Provenance instance
        """
        prov = Provenance(
            run_id=run_id,
            step=step,
            input_data=input_data or {},
            output_data=output_data or {}
        )
        self.db.add(prov)
        self.db.commit()
        self.db.refresh(prov)
        logger.debug(f"Recorded provenance for run {run_id}, step {step}")
        return prov
    
    def get_for_run(self, run_id: str) -> list[Provenance]:
        """Get all provenance records for a run."""
        return self.db.query(Provenance).filter(Provenance.run_id == run_id).order_by(Provenance.created_at).all()
