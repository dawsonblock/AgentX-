"""Append-only event store for runs."""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from db.models import RunEvent
from core.logging import get_logger

logger = get_logger(__name__)


class EventStore:
    """Event store for run events."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def append(
        self,
        run_id: str,
        event_type: str,
        payload: Dict[str, Any],
        actor_kind: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> RunEvent:
        """Append an event to the store.
        
        Args:
            run_id: Run ID
            event_type: Event type
            payload: Event payload
            actor_kind: Optional actor kind (user, system, worker)
            actor_id: Optional actor identifier
            
        Returns:
            Created RunEvent
        """
        # Get next sequence number
        last_event = self.db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.seq.desc()).first()
        seq = 1 if last_event is None else last_event.seq + 1
        
        event = RunEvent(
            run_id=run_id,
            seq=seq,
            type=event_type,
            payload=payload,
            actor_kind=actor_kind,
            actor_id=actor_id
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        logger.debug(f"Event {event_type} appended for run {run_id}")
        return event
    
    def get_events(self, run_id: str, limit: int = 100) -> list[RunEvent]:
        """Get events for a run."""
        return self.db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.seq).limit(limit).all()
