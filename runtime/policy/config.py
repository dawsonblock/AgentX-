"""Security configuration management.

Provides centralized configuration for security policies,
allowing runtime adjustment of security settings.
"""

import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    
    # Subprocess settings
    enforce_allowlist: bool = True
    allow_shell: bool = False
    blocked_commands: List[str] = field(default_factory=lambda: [
        "sudo", "su", "ssh", "scp", "sftp", "curl", "wget", "nc", "netcat"
    ])
    
    # Timeout settings (seconds)
    default_timeout: int = 300
    git_timeout: int = 60
    test_timeout: int = 600
    lint_timeout: int = 120
    build_timeout: int = 300
    max_command_length: int = 8192
    
    # Resource limits
    max_memory_mb: int = 2048
    max_cpu_percent: float = 100.0
    max_disk_mb: int = 1024
    max_output_size_mb: int = 100
    max_concurrent_commands: int = 4
    
    # Path constraints
    allowed_base_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=lambda: [
        "/etc", "/usr/bin", "/usr/sbin", "/bin", "/sbin",
        "/var/log", "/root", "~/.ssh", "~/.aws", "~/.config"
    ])
    
    # Secrets scanning
    secrets_min_severity: str = "low"
    secrets_block_on_critical: bool = True
    secrets_max_matches_per_type: int = 5
    
    # Input validation
    max_input_length: int = 100000
    allowed_content_types: List[str] = field(default_factory=lambda: [
        "text/plain", "text/x-python", "application/json",
        "text/x-diff", "text/x-patch"
    ])
    
    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Load configuration from environment variables."""
        config = cls()
        
        # Subprocess settings
        config.enforce_allowlist = os.getenv("PRODUCT_ENFORCE_ALLOWLIST", "true").lower() == "true"
        config.allow_shell = os.getenv("PRODUCT_ALLOW_SHELL", "false").lower() == "true"
        
        # Timeouts
        config.default_timeout = int(os.getenv("PRODUCT_DEFAULT_TIMEOUT", "300"))
        config.git_timeout = int(os.getenv("PRODUCT_GIT_TIMEOUT", "60"))
        config.test_timeout = int(os.getenv("PRODUCT_TEST_TIMEOUT", "600"))
        
        # Resource limits
        config.max_memory_mb = int(os.getenv("PRODUCT_MAX_MEMORY_MB", "2048"))
        config.max_cpu_percent = float(os.getenv("PRODUCT_MAX_CPU_PERCENT", "100"))
        config.max_disk_mb = int(os.getenv("PRODUCT_MAX_DISK_MB", "1024"))
        
        # Secrets scanning
        config.secrets_min_severity = os.getenv("PRODUCT_SECRETS_MIN_SEVERITY", "low")
        config.secrets_block_on_critical = os.getenv("PRODUCT_SECRETS_BLOCK_CRITICAL", "true").lower() == "true"
        
        # Parse JSON arrays from env
        if "PRODUCT_BLOCKED_COMMANDS" in os.environ:
            try:
                config.blocked_commands = json.loads(os.environ["PRODUCT_BLOCKED_COMMANDS"])
            except json.JSONDecodeError:
                logger.warning("Invalid PRODUCT_BLOCKED_COMMANDS JSON")
        
        if "PRODUCT_BLOCKED_PATHS" in os.environ:
            try:
                config.blocked_paths = json.loads(os.environ["PRODUCT_BLOCKED_PATHS"])
            except json.JSONDecodeError:
                logger.warning("Invalid PRODUCT_BLOCKED_PATHS JSON")
        
        return config
    
    @classmethod
    def from_file(cls, path: str) -> "SecurityConfig":
        """Load configuration from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "enforce_allowlist": self.enforce_allowlist,
            "allow_shell": self.allow_shell,
            "blocked_commands": self.blocked_commands,
            "default_timeout": self.default_timeout,
            "git_timeout": self.git_timeout,
            "test_timeout": self.test_timeout,
            "lint_timeout": self.lint_timeout,
            "build_timeout": self.build_timeout,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "max_disk_mb": self.max_disk_mb,
            "max_output_size_mb": self.max_output_size_mb,
            "max_concurrent_commands": self.max_concurrent_commands,
            "blocked_paths": self.blocked_paths,
            "secrets_min_severity": self.secrets_min_severity,
            "secrets_block_on_critical": self.secrets_block_on_critical,
            "secrets_max_matches_per_type": self.secrets_max_matches_per_type,
            "max_input_length": self.max_input_length,
        }
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate configuration settings.
        
        Returns:
            (is_valid, list of error messages)
        """
        errors = []
        
        if self.default_timeout < 1:
            errors.append("default_timeout must be at least 1 second")
        if self.max_memory_mb < 100:
            errors.append("max_memory_mb must be at least 100 MB")
        if self.max_cpu_percent < 1 or self.max_cpu_percent > 400:
            errors.append("max_cpu_percent must be between 1 and 400")
        if self.max_command_length < 100:
            errors.append("max_command_length must be at least 100 characters")
        if self.secrets_min_severity not in ("critical", "high", "medium", "low"):
            errors.append("secrets_min_severity must be critical, high, medium, or low")
        
        return len(errors) == 0, errors


# Global configuration instance
_config: Optional[SecurityConfig] = None


def get_config() -> SecurityConfig:
    """Get the global security configuration."""
    global _config
    if _config is None:
        _config = SecurityConfig.from_env()
    return _config


def reload_config():
    """Reload configuration from environment."""
    global _config
    _config = SecurityConfig.from_env()
    logger.info("Security configuration reloaded")
    return _config


def set_config(config: SecurityConfig):
    """Set the global security configuration."""
    global _config
    is_valid, errors = config.validate()
    if not is_valid:
        raise ValueError(f"Invalid configuration: {errors}")
    _config = config
    logger.info("Security configuration updated")
