"""API routes for events."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

from ...events.store import EventStore
from ...db.session import get_db

router = APIRouter()


def get_event_store(db: Session = Depends(get_db)) -> EventStore:
    """Get event store with database session."""
    return EventStore(db)


@router.get("/run/{run_id}")
def get_run_events(
    run_id: UUID,
    after_seq: Optional[int] = Query(None, description="Only return events after this sequence number"),
    event_types: Optional[List[str]] = Query(None, description="Filter by event types"),
    limit: int = Query(1000, ge=1, le=10000),
    store: EventStore = Depends(get_event_store)
):
    """Get events for a run.
    
    Args:
        run_id: Run UUID
        after_seq: Only return events after this sequence number
        event_types: Filter by event types
        limit: Maximum events
        store: Event store
        
    Returns:
        List of events
    """
    events = store.get_events(
        run_id=run_id,
        after_seq=after_seq,
        event_types=event_types,
        limit=limit
    )
    return {"run_id": str(run_id), "events": events, "count": len(events)}


@router.get("/run/{run_id}/latest")
def get_latest_event(
    run_id: UUID,
    store: EventStore = Depends(get_event_store)
):
    """Get the latest event for a run.
    
    Args:
        run_id: Run UUID
        store: Event store
        
    Returns:
        Latest event or 404
    """
    event = store.get_latest_event(run_id)
    if not event:
        raise ValueError(f"No events found for run {run_id}")
    return event


@router.get("/run/{run_id}/count")
def get_event_count(
    run_id: UUID,
    store: EventStore = Depends(get_event_store)
):
    """Get event count for a run.
    
    Args:
        run_id: Run UUID
        store: Event store
        
    Returns:
        Event count
    """
    count = store.get_event_count(run_id)
    return {"run_id": str(run_id), "count": count}
