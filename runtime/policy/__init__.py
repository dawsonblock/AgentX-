"""Security policy module for runtime.

Provides security enforcement including:
- Subprocess allowlisting
- Timeout enforcement
- Resource limits
- Input sanitization
- Secrets scanning
"""

from .security import (
    SecurityPolicy,
    SecurityEnforcer,
    get_security_enforcer,
    ALLOWED_COMMANDS,
    BLOCKED_COMMANDS,
)

from .subprocess_wrapper import (
    SecureSubprocess,
    SubprocessResult,
    run_secure,
)

from .secrets_scanner import (
    SecretsScanner,
    SecretMatch,
    SecretType,
    scan_patch,
    get_secrets_scanner,
)

from .config import (
    SecurityConfig,
    get_config,
    reload_config,
)

__all__ = [
    # Security policy
    "SecurityPolicy",
    "SecurityEnforcer",
    "get_security_enforcer",
    "ALLOWED_COMMANDS",
    "BLOCKED_COMMANDS",
    
    # Subprocess wrapper
    "SecureSubprocess",
    "SubprocessResult",
    "run_secure",
    
    # Secrets scanning
    "SecretsScanner",
    "SecretMatch",
    "SecretType",
    "scan_patch",
    "get_secrets_scanner",
    
    # Configuration
    "SecurityConfig",
    "get_config",
    "reload_config",
]
