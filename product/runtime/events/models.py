"""Event database models."""

from sqlalchemy import Column, Integer, String, JSON, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from ..db.base import Base


class RunEvent(Base):
    """An event in the run event log.
    
    Events are append-only and immutable.
    Each event has a monotonically increasing sequence number per run.
    """
    
    __tablename__ = "run_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    type = Column(String(100), nullable=False, index=True)
    actor_kind = Column(String(50), default="runtime")  # runtime, worker, user, system
    actor_id = Column(String(255))
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Ensure unique sequence numbers per run
    __table_args__ = (
        Index('ix_run_events_run_id_seq', 'run_id', 'seq', unique=True),
    )

    def to_dict(self):
        return {
            "event_id": str(self.id),
            "run_id": str(self.run_id),
            "seq": self.seq,
            "type": self.type,
            "actor": {
                "kind": self.actor_kind,
                "id": self.actor_id
            },
            "payload": self.payload or {},
            "timestamp": self.created_at.isoformat() if self.created_at else None,
        }


class EventEnvelope(Base):
    """Schema validation model for event envelopes (not a DB table).
    
    This documents the expected structure of events.
    """
    
    # This is documentation only - events are stored in RunEvent
    EXAMPLE_ENVELOPE = {
        "event_id": "uuid",
        "run_id": "uuid",
        "seq": 17,
        "type": "ToolFinished",
        "timestamp": "2026-03-24T20:00:00Z",
        "actor": {
            "kind": "runtime",
            "id": "executor"
        },
        "payload": {}
    }
