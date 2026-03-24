"""Patch validation.

Validates patches before storage and application.
"""

import subprocess
import tempfile
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_patch(patch: str, repo_path: str) -> bool:
    """Validate patch applies cleanly.
    
    Args:
        patch: Patch diff content
        repo_path: Repository path to validate against
        
    Returns:
        True if patch is valid and applies cleanly
    """
    if not patch or not patch.strip():
        logger.warning("Empty patch")
        return False
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(patch)
        temp_path = f.name
    
    try:
        result = subprocess.run(
            ["git", "apply", "--check", temp_path],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Patch validation passed")
            return True
        else:
            logger.warning(f"Patch validation failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Patch validation error: {e}")
        return False
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def validate_patch_size(patch: str, max_size: int = 100000) -> bool:
    """Check patch size is within limits.
    
    Args:
        patch: Patch diff content
        max_size: Maximum size in characters
        
    Returns:
        True if size is acceptable
    """
    size = len(patch)
    if size > max_size:
        logger.warning(f"Patch size {size} exceeds limit {max_size}")
        return False
    return True


def validate_no_binary(patch: str) -> bool:
    """Check patch doesn't modify binary files.
    
    Args:
        patch: Patch diff content
        
    Returns:
        True if no binary files
    """
    # Check for binary file indicators
    binary_indicators = [
        "Binary files",
        "GIT binary patch",
        "literal 0",
        "delta 0"
    ]
    
    for indicator in binary_indicators:
        if indicator in patch:
            logger.warning(f"Patch contains binary file indicator: {indicator}")
            return False
    
    return True


def validate_patch_complete(patch: str) -> tuple[bool, str]:
    """Complete patch validation.
    
    Args:
        patch: Patch diff content
        
    Returns:
        (is_valid, error_message)
    """
    if not patch or not patch.strip():
        return False, "Empty patch"
    
    if not validate_patch_size(patch):
        return False, "Patch exceeds size limit"
    
    if not validate_no_binary(patch):
        return False, "Patch modifies binary files"
    
    return True, ""
