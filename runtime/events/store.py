"""Event store - append-only event log."""

from uuid import UUID
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import RunEvent
from ..db.session import get_db_session


class EventStore:
    """Store for run events.
    
    All operational events go through this store.
    Events are append-only and immutable.
    """

    def __init__(self, db: Optional[Session] = None):
        """Initialize event store.
        
        Args:
            db: Optional database session
        """
        self.db = db
        self._own_db = db is None

    def _get_db(self) -> Session:
        """Get database session."""
        if self.db is None:
            self.db = get_db_session()
        return self.db

    def append(
        self,
        run_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        actor_kind: str = "runtime",
        actor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Append an event to the log.
        
        Args:
            run_id: Run UUID
            event_type: Type of event
            payload: Event data
            actor_kind: Kind of actor (runtime, worker, user, system)
            actor_id: Actor identifier
            
        Returns:
            Created event data
        """
        db = self._get_db()
        
        # Get next sequence number for this run
        last_event = db.query(RunEvent).filter(
            RunEvent.run_id == run_id
        ).order_by(desc(RunEvent.seq)).first()
        
        seq = (last_event.seq + 1) if last_event else 1
        
        event = RunEvent(
            run_id=run_id,
            seq=seq,
            type=event_type,
            actor_kind=actor_kind,
            actor_id=actor_id,
            payload=payload
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        return event.to_dict()

    def get_events(
        self,
        run_id: UUID,
        after_seq: Optional[int] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get events for a run.
        
        Args:
            run_id: Run UUID
            after_seq: Only return events after this sequence number
            event_types: Filter by event types
            limit: Maximum events to return
            
        Returns:
            List of events
        """
        db = self._get_db()
        
        query = db.query(RunEvent).filter(RunEvent.run_id == run_id)
        
        if after_seq is not None:
            query = query.filter(RunEvent.seq > after_seq)
        
        if event_types:
            query = query.filter(RunEvent.type.in_(event_types))
        
        events = query.order_by(RunEvent.seq).limit(limit).all()
        
        return [event.to_dict() for event in events]

    def get_latest_event(self, run_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the latest event for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Latest event or None
        """
        db = self._get_db()
        
        event = db.query(RunEvent).filter(
            RunEvent.run_id == run_id
        ).order_by(desc(RunEvent.seq)).first()
        
        return event.to_dict() if event else None

    def get_event_count(self, run_id: UUID) -> int:
        """Get total event count for a run.
        
        Args:
            run_id: Run UUID
            
        Returns:
            Number of events
        """
        db = self._get_db()
        return db.query(RunEvent).filter(RunEvent.run_id == run_id).count()
