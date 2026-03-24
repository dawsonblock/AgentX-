"""Test runner tool."""

import subprocess
from core.logging import get_logger

logger = get_logger(__name__)


def run_tests(root: str, test_path: str = "") -> dict:
    """Run tests.
    
    Args:
        root: Repository root
        test_path: Optional specific test path
        
    Returns:
        Dict with success, output, and returncode
    """
    cmd = ["pytest", "-v"] if not test_path else ["pytest", "-v", test_path]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000]
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Test execution timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }
