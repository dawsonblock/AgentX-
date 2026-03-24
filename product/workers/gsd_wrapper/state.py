"""Worker State Manager

Manages the state of a GSD worker instance.
"""

from .contracts import WorkerState


class WorkerStateManager:
    """Manages worker state transitions."""

    # Valid state transitions
    VALID_TRANSITIONS = {
        WorkerState.IDLE: [WorkerState.RUNNING],
        WorkerState.RUNNING: [WorkerState.PAUSED, WorkerState.COMPLETED, WorkerState.FAILED],
        WorkerState.PAUSED: [WorkerState.RUNNING, WorkerState.FAILED],
        WorkerState.COMPLETED: [],
        WorkerState.FAILED: [],
    }

    def __init__(self, run_id: str):
        """Initialize state manager.
        
        Args:
            run_id: Run ID
        """
        self.run_id = run_id
        self._state = WorkerState.IDLE
        self._error: str = ""

    @property
    def state(self) -> WorkerState:
        """Get current state."""
        return self._state

    @property
    def error(self) -> str:
        """Get error message."""
        return self._error

    def can_transition_to(self, target: WorkerState) -> bool:
        """Check if transition to target state is valid.
        
        Args:
            target: Target state
            
        Returns:
            True if transition is valid
        """
        return target in self.VALID_TRANSITIONS.get(self._state, [])

    def transition_to(self, target: WorkerState, error: str = "") -> bool:
        """Transition to target state.
        
        Args:
            target: Target state
            error: Error message (for FAILED state)
            
        Returns:
            True if transition succeeded
            
        Raises:
            ValueError: If transition is invalid
        """
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid state transition from {self._state.value} to {target.value}"
            )
        
        self._state = target
        if error:
            self._error = error
        
        return True

    def is_terminal(self) -> bool:
        """Check if current state is terminal.
        
        Returns:
            True if state is terminal
        """
        return self._state in (WorkerState.COMPLETED, WorkerState.FAILED)
