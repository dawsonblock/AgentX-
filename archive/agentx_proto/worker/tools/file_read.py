"""File read tool."""

import os
from core.logging import get_logger

logger = get_logger(__name__)


def read_file(path: str, max_chars: int = 5000) -> str:
    """Read a file.
    
    Args:
        path: File path
        max_chars: Maximum characters to read
        
    Returns:
        File content
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception as e:
        logger.error(f"Could not read {path}: {e}")
        return f"[Error reading file: {e}]"
