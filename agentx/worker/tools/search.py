"""Search tool."""

import subprocess
import os
from core.logging import get_logger

logger = get_logger(__name__)


def search(root: str, query: str) -> str:
    """Search for a pattern in the repository.
    
    Args:
        root: Repository root
        query: Search query
        
    Returns:
        Search results
    """
    try:
        result = subprocess.run(
            ["grep", "-r", "-n", "-i", query, root],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout[:5000] if result.stdout else "No matches found"
    except subprocess.TimeoutExpired:
        return "Search timed out"
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"[Search error: {e}]"


def search_files(root: str, pattern: str) -> list[str]:
    """Find files matching a pattern.
    
    Args:
        root: Repository root
        pattern: File pattern (e.g., "*.py")
        
    Returns:
        List of matching file paths
    """
    matches = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if pattern in f or f.endswith(pattern.replace("*", "")):
                matches.append(os.path.join(dirpath, f))
    return matches[:20]  # Limit results
