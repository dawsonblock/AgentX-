"""Run state machine with strict transitions."""

from core.errors import InvalidTransition
from core.logging import get_logger

logger = get_logger(__name__)


# Valid state transitions
VALID_TRANSITIONS = {
    "created": ["queued"],
    "queued": ["provisioning"],
    "provisioning": ["context"],
    "context": ["running"],
    "running": ["waiting_approval", "failed"],
    "waiting_approval": ["approved", "rejected"],
    "approved": ["ci"],
    "ci": ["completed", "failed"],
    "rejected": ["failed"],
    "failed": [],  # Terminal state
    "completed": [],  # Terminal state
}


def validate_transition(from_state: str, to_state: str) -> bool:
    """Validate if a state transition is allowed.
    
    Args:
        from_state: Current state
        to_state: Target state
        
    Returns:
        True if transition is valid
        
    Raises:
        InvalidTransition: If transition is not allowed
    """
    allowed = VALID_TRANSITIONS.get(from_state, [])
    if to_state not in allowed:
        raise InvalidTransition(f"{from_state} -> {to_state} not allowed")
    return True


def move(run, to_state: str) -> None:
    """Move a run to a new state.
    
    Args:
        run: Run instance (must have 'state' attribute)
        to_state: Target state
        
    Raises:
        InvalidTransition: If transition is not allowed
    """
    validate_transition(run.state, to_state)
    logger.info(f"Run {run.id}: {run.state} -> {to_state}")
    run.state = to_state


def get_valid_transitions(state: str) -> list[str]:
    """Get list of valid transitions from a state."""
    return VALID_TRANSITIONS.get(state, [])


def is_terminal_state(state: str) -> bool:
    """Check if a state is terminal."""
    return state in ("completed", "failed")
