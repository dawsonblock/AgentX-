"""Custom exceptions for AgentX."""


class AgentXError(Exception):
    """Base exception for all AgentX errors."""
    pass


class InvalidTransition(AgentXError):
    """Raised when attempting an invalid state transition."""
    pass


class PolicyDenied(AgentXError):
    """Raised when a policy check fails."""
    pass


class WorkerError(AgentXError):
    """Raised when the worker encounters an error."""
    pass


class ValidationError(AgentXError):
    """Raised when input validation fails."""
    pass


class ConfigurationError(AgentXError):
    """Raised when configuration is invalid."""
    pass


class LLMError(AgentXError):
    """Raised when LLM API call fails."""
    pass
