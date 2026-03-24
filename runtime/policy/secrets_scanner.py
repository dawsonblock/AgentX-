"""Secrets scanner for detecting sensitive data in patches.

Detects:
- API keys and tokens
- Passwords and credentials
- Private keys
- Connection strings
- Environment files with secrets
"""

import re
import json
from typing import List, Dict, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets that can be detected."""
    API_KEY = "api_key"
    TOKEN = "token"
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    CERTIFICATE = "certificate"
    CONNECTION_STRING = "connection_string"
    AWS_KEY = "aws_key"
    GCP_KEY = "gcp_key"
    AZURE_KEY = "azure_key"
    GITHUB_TOKEN = "github_token"
    SLACK_TOKEN = "slack_token"
    JWT = "jwt"
    BASIC_AUTH = "basic_auth"
    ENV_VAR = "env_var"
    GENERIC_SECRET = "generic_secret"


class SecretMatch(NamedTuple):
    """A detected secret match."""
    secret_type: SecretType
    pattern_name: str
    line_number: int
    column_start: int
    column_end: int
    matched_text: str
    severity: str  # critical, high, medium, low
    description: str


# Secret detection patterns
SECRET_PATTERNS: List[Tuple[str, SecretType, str, str, str]] = [
    # (pattern_name, secret_type, regex, severity, description)
    
    # AWS Keys
    ("aws_access_key_id", SecretType.AWS_KEY,
     r'AKIA[0-9A-Z]{16}',
     "critical", "AWS Access Key ID"),
    
    ("aws_secret_access_key", SecretType.AWS_KEY,
     r'["\'][0-9a-zA-Z/+]{40}["\']',
     "critical", "Potential AWS Secret Key"),
    
    # GitHub Tokens
    ("github_token", SecretType.GITHUB_TOKEN,
     r'gh[pousr]_[A-Za-z0-9_]{36,}',
     "critical", "GitHub Personal Access Token"),
    
    ("github_oauth", SecretType.GITHUB_TOKEN,
     r'gho_[A-Za-z0-9_]{36}',
     "critical", "GitHub OAuth Token"),
    
    # Slack Tokens
    ("slack_token", SecretType.SLACK_TOKEN,
     r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}',
     "critical", "Slack Token"),
    
    ("slack_webhook", SecretType.SLACK_TOKEN,
     r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24}',
     "critical", "Slack Webhook URL"),
    
    # Google API Keys
    ("google_api_key", SecretType.GCP_KEY,
     r'AIza[0-9A-Za-z_-]{35}',
     "high", "Google API Key"),
    
    # Azure Keys
    ("azure_key", SecretType.AZURE_KEY,
     r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
     "medium", "Potential Azure GUID/Key"),
    
    # Private Keys
    ("private_key_rsa", SecretType.PRIVATE_KEY,
     r'-----BEGIN RSA PRIVATE KEY-----',
     "critical", "RSA Private Key"),
    
    ("private_key_dsa", SecretType.PRIVATE_KEY,
     r'-----BEGIN DSA PRIVATE KEY-----',
     "critical", "DSA Private Key"),
    
    ("private_key_ec", SecretType.PRIVATE_KEY,
     r'-----BEGIN EC PRIVATE KEY-----',
     "critical", "EC Private Key"),
    
    ("private_key_openssh", SecretType.PRIVATE_KEY,
     r'-----BEGIN OPENSSH PRIVATE KEY-----',
     "critical", "OpenSSH Private Key"),
    
    ("private_key_pkcs8", SecretType.PRIVATE_KEY,
     r'-----BEGIN PRIVATE KEY-----',
     "critical", "PKCS8 Private Key"),
    
    ("private_key_pgp", SecretType.PRIVATE_KEY,
     r'-----BEGIN PGP PRIVATE KEY BLOCK-----',
     "critical", "PGP Private Key"),
    
    # Certificates
    ("certificate", SecretType.CERTIFICATE,
     r'-----BEGIN CERTIFICATE-----',
     "high", "X.509 Certificate"),
    
    # JWT Tokens
    ("jwt_token", SecretType.JWT,
     r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
     "high", "JSON Web Token (JWT)"),
    
    # API Keys (generic patterns)
    ("api_key_generic", SecretType.API_KEY,
     r'[aA][pP][iI]_?[kK][eE][yY]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{16,}["\']?',
     "medium", "Potential API Key"),
    
    ("secret_generic", SecretType.GENERIC_SECRET,
     r'[sS][eE][cC][rR][eE][tT]_?[kK][eE][yY]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{8,}["\']?',
     "medium", "Potential Secret Key"),
    
    # Passwords
    ("password_assignment", SecretType.PASSWORD,
     r'[pP][aA][sS][sS][wW][oO][rR][dD]["\']?\s*[:=]\s*["\'][^"\']{4,}["\']',
     "high", "Password in code"),
    
    ("password_url", SecretType.PASSWORD,
     r'[a-zA-Z]+://[^:]+:[^@]+@[a-zA-Z0-9]',
     "critical", "Password in URL"),
    
    # Basic Auth
    ("basic_auth", SecretType.BASIC_AUTH,
     r'Basic\s+[A-Za-z0-9+/]{20,}={0,2}',
     "high", "HTTP Basic Auth"),
    
    # Bearer Tokens
    ("bearer_token", SecretType.TOKEN,
     r'[bB][eE][aA][rR][eE][rR]\s+[a-zA-Z0-9_\-\.=]+',
     "high", "Bearer Token"),
    
    # Database Connection Strings
    ("postgres_connection", SecretType.CONNECTION_STRING,
     r'postgres(ql)?://[^:]+:[^@]+@[^/]+',
     "critical", "PostgreSQL Connection String"),
    
    ("mysql_connection", SecretType.CONNECTION_STRING,
     r'mysql://[^:]+:[^@]+@[^/]+',
     "critical", "MySQL Connection String"),
    
    ("mongodb_connection", SecretType.CONNECTION_STRING,
     r'mongodb(\+srv)?://[^:]+:[^@]+@[^/]+',
     "critical", "MongoDB Connection String"),
    
    ("redis_connection", SecretType.CONNECTION_STRING,
     r'redis://:[^@]+@[^/]+',
     "high", "Redis Connection String"),
    
    # Environment variables with secrets
    ("env_secret", SecretType.ENV_VAR,
     r'export\s+[A-Z_]*(?:SECRET|KEY|TOKEN|PASSWORD|PASS|PWD)[A-Z_]*=[^\s]+',
     "medium", "Secret in environment variable"),
    
    # Generic high-entropy strings (last resort)
    ("high_entropy_base64", SecretType.GENERIC_SECRET,
     r'[A-Za-z0-9+/]{40,}={0,2}',
     "low", "High-entropy string (potential secret)"),
    
    ("high_entropy_hex", SecretType.GENERIC_SECRET,
     r'[0-9a-f]{32,}',
     "low", "High-entropy hex string (potential secret)"),
]

# Compiled patterns for efficiency
COMPILED_PATTERNS: List[Tuple[str, SecretType, re.Pattern, str, str]] = []


def _compile_patterns():
    """Compile regex patterns for efficiency."""
    global COMPILED_PATTERNS
    if not COMPILED_PATTERNS:
        for name, secret_type, pattern, severity, description in SECRET_PATTERNS:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                COMPILED_PATTERNS.append((name, secret_type, compiled, severity, description))
            except re.error as e:
                logger.warning(f"Failed to compile pattern {name}: {e}")


class SecretsScanner:
    """Scanner for detecting secrets in text content."""
    
    def __init__(self, 
                 min_severity: str = "low",
                 max_matches_per_type: int = 5,
                 block_on_critical: bool = True):
        """Initialize the secrets scanner.
        
        Args:
            min_severity: Minimum severity to report (critical, high, medium, low)
            max_matches_per_type: Maximum matches per secret type
            block_on_critical: Whether to block when critical secrets found
        """
        self.min_severity = min_severity
        self.max_matches_per_type = max_matches_per_type
        self.block_on_critical = block_on_critical
        self._severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        # Compile patterns on first use
        _compile_patterns()
    
    def scan_text(self, text: str, filename: str = "<unknown>") -> Tuple[List[SecretMatch], bool]:
        """Scan text for secrets.
        
        Args:
            text: Text content to scan
            filename: Name of file being scanned (for context)
            
        Returns:
            (matches, should_block) - List of matches and whether to block
        """
        matches: List[SecretMatch] = []
        should_block = False
        matches_by_type: Dict[SecretType, int] = {}
        
        lines = text.split("\n")
        
        for line_num, line in enumerate(lines, start=1):
            for pattern_name, secret_type, pattern, severity, description in COMPILED_PATTERNS:
                # Check severity threshold
                if self._severity_order.get(severity, 0) < self._severity_order.get(self.min_severity, 0):
                    continue
                
                # Check max matches per type
                if matches_by_type.get(secret_type, 0) >= self.max_matches_per_type:
                    continue
                
                # Search for matches
                for match in pattern.finditer(line):
                    matched_text = match.group(0)
                    
                    # Additional validation to reduce false positives
                    if not self._validate_match(matched_text, secret_type):
                        continue
                    
                    secret_match = SecretMatch(
                        secret_type=secret_type,
                        pattern_name=pattern_name,
                        line_number=line_num,
                        column_start=match.start(),
                        column_end=match.end(),
                        matched_text=matched_text[:100],  # Truncate long matches
                        severity=severity,
                        description=description
                    )
                    
                    matches.append(secret_match)
                    matches_by_type[secret_type] = matches_by_type.get(secret_type, 0) + 1
                    
                    # Check if we should block
                    if severity == "critical" and self.block_on_critical:
                        should_block = True
                    
                    logger.warning(
                        f"Secret detected in {filename}:{line_num}: "
                        f"{description} ({severity})"
                    )
        
        return matches, should_block
    
    def scan_diff(self, diff_text: str) -> Tuple[List[SecretMatch], bool]:
        """Scan a git diff for secrets.
        
        Only scans added lines (starting with +) to avoid flagging
        secrets that are being removed.
        
        Args:
            diff_text: Git diff content
            
        Returns:
            (matches, should_block)
        """
        # Extract only added lines from diff
        added_lines = []
        current_file = "<unknown>"
        
        for line in diff_text.split("\n"):
            if line.startswith("diff --git"):
                # Extract filename
                parts = line.split()
                if len(parts) >= 3:
                    current_file = parts[2][2:]  # Remove 'b/' prefix
            elif line.startswith("+") and not line.startswith("+++"):
                # Added line (excluding the +++ header)
                added_lines.append((current_file, line[1:]))  # Remove '+' prefix
        
        # Scan only added lines
        all_matches = []
        should_block = False
        
        for filename, line in added_lines:
            matches, block = self.scan_text(line, filename)
            all_matches.extend(matches)
            if block:
                should_block = True
        
        return all_matches, should_block
    
    def _validate_match(self, matched_text: str, secret_type: SecretType) -> bool:
        """Validate a potential match to reduce false positives.
        
        Args:
            matched_text: The matched text
            secret_type: Type of secret
            
        Returns:
            True if valid, False if false positive
        """
        # Skip if match is too short
        if len(matched_text) < 8:
            return False
        
        # Skip common false positives
        false_positive_patterns = [
            r'example',
            r'test',
            r'fake',
            r'dummy',
            r'placeholder',
            r'xxxxxxxx',
            r'00000000',
            r'password123',
            r'changeme',
            r'secret_key_here',
        ]
        
        lower_text = matched_text.lower()
        for pattern in false_positive_patterns:
            if pattern in lower_text:
                return False
        
        # Skip if it's a variable name ending in _KEY or _SECRET
        # but not the actual value
        if secret_type in (SecretType.API_KEY, SecretType.GENERIC_SECRET):
            if matched_text.count("=") == 0 and matched_text.count(":") == 0:
                # This might just be a variable name, not the value
                if matched_text.isidentifier():
                    return False
        
        return True
    
    def format_report(self, matches: List[SecretMatch], filename: str = "patch") -> str:
        """Format a report of detected secrets.
        
        Args:
            matches: List of secret matches
            filename: Name of file being reported on
            
        Returns:
            Formatted report string
        """
        if not matches:
            return "No secrets detected."
        
        lines = [f"Secret Scan Results for {filename}", "=" * 50, ""]
        
        # Group by severity
        by_severity: Dict[str, List[SecretMatch]] = {}
        for match in matches:
            by_severity.setdefault(match.severity, []).append(match)
        
        for severity in ["critical", "high", "medium", "low"]:
            if severity not in by_severity:
                continue
            
            lines.append(f"\n{severity.upper()} ({len(by_severity[severity])} found):")
            lines.append("-" * 40)
            
            for match in by_severity[severity]:
                lines.append(
                    f"  Line {match.line_number}: {match.description}"
                )
                lines.append(
                    f"    Pattern: {match.pattern_name}"
                )
                lines.append(
                    f"    Text: {match.matched_text[:50]}..."
                    if len(match.matched_text) > 50
                    else f"    Text: {match.matched_text}"
                )
                lines.append("")
        
        critical_count = len(by_severity.get("critical", []))
        if critical_count > 0:
            lines.append(f"\n⚠️  {critical_count} CRITICAL secret(s) detected!")
            lines.append("This patch will be blocked from promotion.")
        
        return "\n".join(lines)


# Global scanner instance
_default_scanner: Optional[SecretsScanner] = None


def get_secrets_scanner(**kwargs) -> SecretsScanner:
    """Get the global secrets scanner instance."""
    global _default_scanner
    if _default_scanner is None:
        _default_scanner = SecretsScanner(**kwargs)
    return _default_scanner


def scan_patch(diff_text: str) -> Tuple[List[SecretMatch], bool, str]:
    """Convenience function to scan a patch for secrets.
    
    Args:
        diff_text: Git diff content
        
    Returns:
        (matches, should_block, report)
    """
    scanner = get_secrets_scanner()
    matches, should_block = scanner.scan_diff(diff_text)
    report = scanner.format_report(matches)
    return matches, should_block, report
