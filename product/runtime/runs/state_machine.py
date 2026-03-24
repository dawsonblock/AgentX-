"""Run state machine - defines valid state transitions."""

from typing import Set, Dict, List

# Valid state transitions for v1
# Format: current_state -> [valid_target_states]
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "created": ["queued", "cancelled"],
    "queued": ["provisioning", "cancelled"],
    "provisioning": ["context_building", "failed", "cancelled"],
    "context_building": ["running", "failed", "cancelled"],
    "running": ["waiting_approval", "paused", "failed", "completed", "cancelled"],
    "waiting_approval": ["running", "failed", "cancelled"],
    "paused": ["running", "failed", "cancelled"],
    "failed": [],
    "completed": [],
    "cancelled": [],
}

# Terminal states
TERMINAL_STATES: Set[str] = {"failed", "completed", "cancelled"}

# States that allow tool execution
EXECUTABLE_STATES: Set[str] = {"running", "waiting_approval"}


def can_transition(current_state: str, target_state: str) -> bool:
    """Check if a state transition is valid.
    
    Args:
        current_state: Current run state
        target_state: Desired target state
        
    Returns:
        True if transition is valid, False otherwise
    """
    if current_state not in VALID_TRANSITIONS:
        return False
    return target_state in VALID_TRANSITIONS[current_state]


def get_valid_transitions(current_state: str) -> List[str]:
    """Get list of valid transitions from a state.
    
    Args:
        current_state: Current run state
        
    Returns:
        List of valid target states
    """
    return VALID_TRANSITIONS.get(current_state, [])


def is_terminal_state(state: str) -> bool:
    """Check if state is terminal (no further transitions allowed).
    
    Args:
        state: State to check
        
    Returns:
        True if terminal, False otherwise
    """
    return state in TERMINAL_STATES


def can_execute_tools(state: str) -> bool:
    """Check if run state allows tool execution.
    
    Args:
        state: Current run state
        
    Returns:
        True if tools can be executed, False otherwise
    """
    return state in EXECUTABLE_STATES


def validate_transition(current_state: str, target_state: str) -> None:
    """Validate a state transition, raising exception if invalid.
    
    Args:
        current_state: Current run state
        target_state: Desired target state
        
    Raises:
        ValueError: If transition is invalid
    """
    if is_terminal_state(current_state):
        raise ValueError(
            f"Cannot transition from terminal state '{current_state}'"
        )
    
    if not can_transition(current_state, target_state):
        valid = get_valid_transitions(current_state)
        raise ValueError(
            f"Invalid transition from '{current_state}' to '{target_state}'. "
            f"Valid transitions: {valid}"
        )
