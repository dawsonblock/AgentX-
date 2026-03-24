"""Security policy enforcement for the runtime.

Provides:
- Subprocess allowlist enforcement
- Timeout configuration
- Resource limits
- Input validation
- Path sandboxing
"""

import re
import shlex
from typing import List, Set, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Allowed subprocess commands (whitelist)
ALLOWED_COMMANDS: Set[str] = {
    # Version control
    "git",
    # Python tooling
    "python",
    "python3",
    "pytest",
    "pip",
    "mypy",
    "flake8",
    "black",
    "pylint",
    "bandit",
    # Node.js tooling
    "node",
    "npm",
    "npx",
    "eslint",
    "tsc",
    "jest",
    # Go tooling
    "go",
    "gofmt",
    "golint",
    "goimports",
    # Rust tooling
    "cargo",
    "rustfmt",
    "clippy",
    "rustc",
    # Java tooling
    "javac",
    "java",
    "mvn",
    "gradle",
    # General utilities (safe subset)
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "ls",
    "pwd",
    "wc",
    "diff",
    "echo",
    "mkdir",
    "touch",
    "rm",
    "cp",
    "mv",
    "which",
    "file",
    "sort",
    "uniq",
    "cut",
    "tr",
    "sed",
    "awk",
}

# Dangerous commands that should never be allowed
BLOCKED_COMMANDS: Set[str] = {
    "sudo",
    "su",
    "ssh",
    "scp",
    "sftp",
    "curl",
    "wget",
    "nc",
    "netcat",
    "telnet",
    "bash",
    "sh",
    "zsh",
    "fish",
    "eval",
    "exec",
    "source",
    ".",
    '\"',
    "|",
    "&",
    ";",
    "$",
    "`",
}

# Dangerous shell metacharacters
DANGEROUS_CHARS: Set[str] = {
    ";", "&", "|", "$", "`", "\\", "<", ">", "(", ")", "{", "}", "[", "]",
    "*", "?", "~", "!", "#", "%", "^",
}

# Patterns that might indicate command injection
DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r'\$\{.*\}', re.IGNORECASE),  # ${...} variable expansion
    re.compile(r'\$\(.*\)', re.IGNORECASE),  # $(...) command substitution
    re.compile(r'`.*`', re.IGNORECASE),       # `...` command substitution
    re.compile(r'\|\|', re.IGNORECASE),      # || operator
    re.compile(r'&&', re.IGNORECASE),         # && operator
    re.compile(r'>>', re.IGNORECASE),         # append redirect
    re.compile(r'2>&1', re.IGNORECASE),       # stderr redirect
    re.compile(r'/dev/(tcp|udp|stdin|stdout|stderr)', re.IGNORECASE),
    re.compile(r'base64\s+-d', re.IGNORECASE),  # base64 decode
    re.compile(r'eval\s+', re.IGNORECASE),      # eval
    re.compile(r'exec\s+', re.IGNORECASE),      # exec
]


@dataclass
class SecurityPolicy:
    """Security policy configuration."""
    
    # Timeout configuration (seconds)
    default_timeout: int = 300  # 5 minutes
    git_timeout: int = 60
    test_timeout: int = 600  # 10 minutes for tests
    lint_timeout: int = 120
    build_timeout: int = 300
    
    # Resource limits
    max_memory_mb: int = 2048  # 2GB
    max_cpu_percent: float = 100.0  # 100% of one core
    max_disk_mb: int = 1024  # 1GB temp space
    max_output_size_mb: int = 100  # 100MB output capture
    
    # Execution limits
    max_concurrent_commands: int = 4
    max_command_length: int = 8192  # 8KB
    
    # Path constraints
    allowed_base_paths: List[str] = None
    blocked_paths: List[str] = None
    
    # Allowlist enforcement
    enforce_allowlist: bool = True
    allow_shell: bool = False  # Never allow shell=True
    
    def __post_init__(self):
        if self.allowed_base_paths is None:
            self.allowed_base_paths = []
        if self.blocked_paths is None:
            self.blocked_paths = [
                "/etc",
                "/usr/bin",
                "/usr/sbin",
                "/bin",
                "/sbin",
                "/var/log",
                "/root",
                "~/.ssh",
                "~/.aws",
                "~/.config",
            ]


class SecurityEnforcer:
    """Enforces security policies for subprocess execution."""
    
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self._active_commands: Dict[str, Any] = {}
    
    def validate_command(self, command: List[str]) -> tuple[bool, str]:
        """Validate a command against security policies.
        
        Args:
            command: Command as list of arguments
            
        Returns:
            (is_valid, error_message)
        """
        if not command:
            return False, "Empty command"
        
        # Check command length
        cmd_str = " ".join(command)
        if len(cmd_str) > self.policy.max_command_length:
            return False, f"Command too long ({len(cmd_str)} > {self.policy.max_command_length})"
        
        # Get base command
        base_cmd = command[0]
        
        # Check for shell metacharacters in command
        for arg in command:
            if any(c in arg for c in DANGEROUS_CHARS):
                return False, f"Dangerous characters in argument: {arg}"
        
        # Check for command injection patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(cmd_str):
                return False, f"Potential command injection detected: {cmd_str}"
        
        # Check if base command is in blocked list
        if base_cmd in BLOCKED_COMMANDS:
            return False, f"Command '{base_cmd}' is blocked"
        
        # Check allowlist
        if self.policy.enforce_allowlist:
            if base_cmd not in ALLOWED_COMMANDS:
                return False, f"Command '{base_cmd}' not in allowlist"
        
        # Validate arguments don't contain dangerous patterns
        for arg in command[1:]:
            # Block arguments that look like command injection
            if arg.startswith("$") or arg.startswith("`") or ";" in arg or "|" in arg:
                return False, f"Suspicious argument: {arg}"
            
            # Block path traversal attempts
            if "../" in arg or "..\\" in arg:
                # Allow if it's a legitimate relative path within worktree
                if not self._is_safe_path(arg):
                    return False, f"Path traversal detected: {arg}"
        
        return True, ""
    
    def validate_shell_command(self, command: str) -> tuple[bool, str]:
        """Validate a shell command string.
        
        Shell commands are generally blocked for security.
        Use list-based commands instead.
        
        Args:
            command: Shell command string
            
        Returns:
            (is_valid, error_message)
        """
        if not self.policy.allow_shell:
            return False, "Shell commands are disabled. Use list-based commands."
        
        # Even if allowed, validate heavily
        if len(command) > self.policy.max_command_length:
            return False, f"Command too long ({len(command)} > {self.policy.max_command_length})"
        
        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return False, f"Dangerous pattern in command: {command}"
        
        # Parse and validate
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return False, f"Invalid shell syntax: {e}"
        
        return self.validate_command(parts)
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is safe (no traversal outside allowed base)."""
        try:
            resolved = Path(path).resolve()
            
            # Check against blocked paths
            for blocked in self.policy.blocked_paths:
                blocked_path = Path(blocked).expanduser().resolve()
                if resolved == blocked_path or str(resolved).startswith(str(blocked_path)):
                    return False
            
            # Check against allowed base paths (if specified)
            if self.policy.allowed_base_paths:
                for allowed in self.policy.allowed_base_paths:
                    allowed_path = Path(allowed).resolve()
                    if str(resolved).startswith(str(allowed_path)):
                        return True
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Path validation error for {path}: {e}")
            return False
    
    def validate_path(self, path: str, worktree_path: Optional[str] = None) -> tuple[bool, str]:
        """Validate that a path is within allowed boundaries.
        
        Args:
            path: Path to validate
            worktree_path: Optional worktree path to constrain to
            
        Returns:
            (is_valid, error_message)
        """
        try:
            resolved = Path(path).resolve()
            
            # If worktree specified, path must be within it
            if worktree_path:
                worktree = Path(worktree_path).resolve()
                try:
                    resolved.relative_to(worktree)
                except ValueError:
                    return False, f"Path {path} is outside worktree {worktree_path}"
            
            # Check blocked paths
            for blocked in self.policy.blocked_paths:
                blocked_path = Path(blocked).expanduser().resolve()
                if resolved == blocked_path:
                    return False, f"Path {path} is blocked"
                if str(resolved).startswith(str(blocked_path)):
                    return False, f"Path {path} is in blocked directory"
            
            # Check for traversal attempts
            if ".." in str(resolved):
                # Additional check for traversal
                normalized = Path(path).expanduser().resolve()
                if worktree_path:
                    worktree = Path(worktree_path).resolve()
                    if not str(normalized).startswith(str(worktree)):
                        return False, f"Path traversal detected: {path}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Path validation error: {e}"
    
    def get_timeout_for_command(self, command: List[str]) -> int:
        """Get appropriate timeout for a command type."""
        if not command:
            return self.policy.default_timeout
        
        base_cmd = command[0].lower()
        
        if base_cmd == "git":
            return self.policy.git_timeout
        elif base_cmd in ("pytest", "python", "python3", "npm", "jest"):
            # Check if this looks like a test command
            if any(arg in command for arg in ["test", "pytest", "jest", "--test"]):
                return self.policy.test_timeout
            return self.policy.default_timeout
        elif base_cmd in ("mypy", "flake8", "eslint", "pylint", "golint"):
            return self.policy.lint_timeout
        elif base_cmd in ("go", "cargo", "mvn", "gradle", "npm"):
            # Check if this is a build command
            if any(arg in ["build", "compile"] for arg in command):
                return self.policy.build_timeout
            return self.policy.default_timeout
        
        return self.policy.default_timeout
    
    def sanitize_input(self, text: str, max_length: int = 10000) -> str:
        """Sanitize user input to prevent injection attacks.
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Truncate
        if len(text) > max_length:
            text = text[:max_length]
        
        # Remove null bytes
        text = text.replace("\x00", "")
        
        # Remove control characters except common whitespace
        text = "".join(c for c in text if c == "\n" or c == "\r" or c == "\t" or ord(c) >= 32)
        
        return text


# Global security enforcer instance
_security_enforcer: Optional[SecurityEnforcer] = None


def get_security_enforcer(policy: Optional[SecurityPolicy] = None) -> SecurityEnforcer:
    """Get the global security enforcer instance."""
    global _security_enforcer
    if _security_enforcer is None:
        _security_enforcer = SecurityEnforcer(policy)
    return _security_enforcer


def reset_security_enforcer():
    """Reset the global security enforcer (for testing)."""
    global _security_enforcer
    _security_enforcer = None
