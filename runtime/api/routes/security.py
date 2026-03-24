"""API routes for security features."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from ...policy import scan_patch, get_secrets_scanner, SecretsScanner
from ...policy.config import get_config, SecurityConfig, reload_config

router = APIRouter()


class ScanRequest(BaseModel):
    """Request to scan content for secrets."""
    content: str
    filename: Optional[str] = "<unknown>"


class SecretMatchResponse(BaseModel):
    """Detected secret match response."""
    secret_type: str
    pattern_name: str
    line_number: int
    column_start: int
    column_end: int
    matched_text: str
    severity: str
    description: str


class ScanResponse(BaseModel):
    """Scan response."""
    found_secrets: bool
    should_block: bool
    matches: List[SecretMatchResponse]
    report: str


class PatchScanRequest(BaseModel):
    """Request to scan a patch/diff for secrets."""
    diff_text: str


class SecurityConfigResponse(BaseModel):
    """Security configuration response."""
    enforce_allowlist: bool
    allow_shell: bool
    blocked_commands: List[str]
    default_timeout: int
    git_timeout: int
    test_timeout: int
    lint_timeout: int
    build_timeout: int
    max_memory_mb: int
    max_cpu_percent: float
    max_disk_mb: int
    max_output_size_mb: int
    max_concurrent_commands: int
    blocked_paths: List[str]
    secrets_min_severity: str
    secrets_block_on_critical: bool
    secrets_max_matches_per_type: int
    max_input_length: int


@router.post("/scan", response_model=ScanResponse)
def scan_content(request: ScanRequest):
    """Scan content for secrets.
    
    Args:
        request: Scan request with content and optional filename
        
    Returns:
        Scan results with detected secrets
    """
    scanner = get_secrets_scanner()
    matches, should_block = scanner.scan_text(request.content, request.filename)
    report = scanner.format_report(matches, request.filename)
    
    return ScanResponse(
        found_secrets=len(matches) > 0,
        should_block=should_block,
        matches=[
            SecretMatchResponse(
                secret_type=m.secret_type.value,
                pattern_name=m.pattern_name,
                line_number=m.line_number,
                column_start=m.column_start,
                column_end=m.column_end,
                matched_text=m.matched_text,
                severity=m.severity,
                description=m.description
            )
            for m in matches
        ],
        report=report
    )


@router.post("/scan/patch", response_model=ScanResponse)
def scan_patch_endpoint(request: PatchScanRequest):
    """Scan a git diff/patch for secrets.
    
    Only scans added lines (lines starting with +) to avoid
    flagging secrets that are being removed.
    
    Args:
        request: Patch scan request with diff text
        
    Returns:
        Scan results with detected secrets
    """
    matches, should_block, report = scan_patch(request.diff_text)
    
    return ScanResponse(
        found_secrets=len(matches) > 0,
        should_block=should_block,
        matches=[
            SecretMatchResponse(
                secret_type=m.secret_type.value,
                pattern_name=m.pattern_name,
                line_number=m.line_number,
                column_start=m.column_start,
                column_end=m.column_end,
                matched_text=m.matched_text,
                severity=m.severity,
                description=m.description
            )
            for m in matches
        ],
        report=report
    )


@router.get("/config", response_model=SecurityConfigResponse)
def get_security_config():
    """Get current security configuration.
    
    Returns:
        Security configuration settings
    """
    config = get_config()
    return SecurityConfigResponse(**config.to_dict())


@router.post("/config/reload")
def reload_security_config():
    """Reload security configuration from environment.
    
    Returns:
        Success message
    """
    reload_config()
    return {"message": "Security configuration reloaded"}


@router.get("/allowed-commands")
def get_allowed_commands():
    """Get list of allowed subprocess commands.
    
    Returns:
        List of allowed commands
    """
    from ...policy import ALLOWED_COMMANDS
    return {
        "allowed_commands": sorted(list(ALLOWED_COMMANDS)),
        "count": len(ALLOWED_COMMANDS)
    }


@router.get("/blocked-commands")
def get_blocked_commands():
    """Get list of blocked subprocess commands.
    
    Returns:
        List of blocked commands
    """
    from ...policy import BLOCKED_COMMANDS
    config = get_config()
    return {
        "blocked_commands": sorted(list(config.blocked_commands)),
        "count": len(config.blocked_commands)
    }


class ValidateCommandRequest(BaseModel):
    """Request to validate a command."""
    command: List[str]


class ValidateCommandResponse(BaseModel):
    """Command validation response."""
    valid: bool
    error_message: Optional[str] = None


@router.post("/validate-command", response_model=ValidateCommandResponse)
def validate_command(request: ValidateCommandRequest):
    """Validate if a command is allowed by security policy.
    
    Args:
        request: Command validation request
        
    Returns:
        Validation result
    """
    from ...policy import get_security_enforcer
    
    enforcer = get_security_enforcer()
    is_valid, error_msg = enforcer.validate_command(request.command)
    
    return ValidateCommandResponse(
        valid=is_valid,
        error_message=error_msg if not is_valid else None
    )


@router.post("/validate-path")
def validate_path(path: str, worktree_path: Optional[str] = None):
    """Validate if a path is safe.
    
    Args:
        path: Path to validate
        worktree_path: Optional worktree to constrain to
        
    Returns:
        Validation result
    """
    from ...policy import get_security_enforcer
    
    enforcer = get_security_enforcer()
    is_valid, error_msg = enforcer.validate_path(path, worktree_path)
    
    return {
        "valid": is_valid,
        "path": path,
        "worktree_constrained": worktree_path is not None,
        "error_message": error_msg if not is_valid else None
    }
