"""Simple in-memory queue for background execution.

For production, replace with Redis/RQ.
"""

import time
from typing import Callable, List
from core.config import Settings
from core.logging import get_logger

logger = get_logger(__name__)

# In-memory queue
QUEUE: List[str] = []


def enqueue(run_id: str) -> None:
    """Add a run to the queue."""
    QUEUE.append(run_id)
    logger.info(f"Enqueued run {run_id}")


def dequeue() -> str:
    """Remove and return a run from the queue."""
    return QUEUE.pop(0)


def worker_loop(executor_factory: Callable[[], Callable[[str], None]]) -> None:
    """Worker loop that processes queue items.
    
    Args:
        executor_factory: Factory function that returns an executor function
    """
    logger.info("Starting worker loop...")
    
    while True:
        if QUEUE:
            run_id = dequeue()
            logger.info(f"Processing run {run_id}")
            
            try:
                executor = executor_factory()
                executor(run_id)
            except Exception as e:
                logger.error(f"Failed to execute run {run_id}: {e}")
        
        time.sleep(Settings.QUEUE_POLL_SEC)
