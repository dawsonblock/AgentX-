"""Tool implementations for the executor.

All side effects happen here. This is the hard boundary.
"""

import os
import subprocess
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class ToolError(Exception):
    """Error executing a tool."""
    
    def __init__(self, message: str, exit_code: int = 1, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


def run_tests(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run tests in the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - test_path: Optional specific test path
            - runner: Test runner (pytest, unittest, etc.)
    
    Returns:
        Tool result
    """
    worktree_path = args.get("worktree_path", ".")
    test_path = args.get("test_path", "")
    runner = args.get("runner", "pytest")
    
    cmd = [runner]
    if test_path:
        cmd.append(test_path)
    cmd.extend(["-v", "--tb=short"])
    
    proc = subprocess.run(
        cmd,
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_ms": 0,  # Would track actual duration
        "files_touched": [],
        "artifacts_produced": []
    }


def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read a file from the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - path: File path (relative to worktree)
            - limit: Optional line limit
    
    Returns:
        Tool result with file content
    """
    worktree_path = args.get("worktree_path", ".")
    file_path = args.get("path")
    limit = args.get("limit")
    
    if not file_path:
        raise ToolError("path is required")
    
    # Ensure path is within worktree
    full_path = Path(worktree_path) / file_path
    full_path = full_path.resolve()
    worktree_resolved = Path(worktree_path).resolve()
    
    if not str(full_path).startswith(str(worktree_resolved)):
        raise ToolError(f"Path '{file_path}' is outside worktree")
    
    if not full_path.exists():
        raise ToolError(f"File not found: {file_path}")
    
    content = full_path.read_text()
    
    if limit:
        lines = content.split("\n")[:limit]
        content = "\n".join(lines)
    
    return {
        "exit_code": 0,
        "content": content,
        "path": str(file_path),
        "size_bytes": full_path.stat().st_size,
        "duration_ms": 0
    }


def read_file_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read multiple files from the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - paths: List of file paths
            - limit: Optional line limit per file
    
    Returns:
        Tool result with file contents
    """
    worktree_path = args.get("worktree_path", ".")
    paths = args.get("paths", [])
    limit = args.get("limit")
    
    results = []
    for path in paths:
        try:
            result = read_file({
                "worktree_path": worktree_path,
                "path": path,
                "limit": limit
            })
            results.append({
                "path": path,
                "content": result["content"],
                "success": True
            })
        except ToolError as e:
            results.append({
                "path": path,
                "error": str(e),
                "success": False
            })
    
    return {
        "exit_code": 0,
        "files": results,
        "success_count": sum(1 for r in results if r["success"]),
        "failure_count": sum(1 for r in results if not r["success"]),
        "duration_ms": 0
    }


def search_text(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search for text in the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - query: Search query
            - path_filter: Optional path glob filter
    
    Returns:
        Tool result with matches
    """
    worktree_path = args.get("worktree_path", ".")
    query = args.get("query", "")
    path_filter = args.get("path_filter", "")
    
    # Use grep for text search
    cmd = ["grep", "-r", "-n", "-I", "--include=*.py", "--include=*.ts", "--include=*.js"]
    if path_filter:
        cmd.extend(["--include", path_filter])
    cmd.extend([query, "."])
    
    proc = subprocess.run(
        cmd,
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # grep returns 1 when no matches found
    if proc.returncode > 1:
        raise ToolError(f"Search failed: {proc.stderr}", exit_code=proc.returncode)
    
    matches = []
    for line in proc.stdout.split("\n"):
        if line.strip():
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "path": parts[0],
                    "line": int(parts[1]),
                    "text": parts[2]
                })
    
    return {
        "exit_code": 0,
        "query": query,
        "matches": matches,
        "match_count": len(matches),
        "duration_ms": 0
    }


def git_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get git status of the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
    
    Returns:
        Tool result with status
    """
    worktree_path = args.get("worktree_path", ".")
    
    proc = subprocess.run(
        ["git", "status", "--porcelain", "-b"],
        cwd=worktree_path,
        capture_output=True,
        text=True
    )
    
    if proc.returncode != 0:
        raise ToolError(f"git status failed: {proc.stderr}")
    
    lines = proc.stdout.split("\n")
    
    # Parse status
    branch_line = lines[0] if lines else ""
    status_lines = lines[1:] if len(lines) > 1 else []
    
    files = []
    for line in status_lines:
        if line.strip():
            status = line[:2]
            path = line[3:] if len(line) > 3 else ""
            files.append({"status": status, "path": path})
    
    return {
        "exit_code": 0,
        "branch_info": branch_line,
        "files": files,
        "has_changes": len(files) > 0,
        "duration_ms": 0
    }


def git_diff(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get git diff of the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - staged: Show staged changes
    
    Returns:
        Tool result with diff
    """
    worktree_path = args.get("worktree_path", ".")
    staged = args.get("staged", False)
    
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    
    proc = subprocess.run(
        cmd,
        cwd=worktree_path,
        capture_output=True,
        text=True
    )
    
    if proc.returncode != 0:
        raise ToolError(f"git diff failed: {proc.stderr}")
    
    return {
        "exit_code": 0,
        "diff": proc.stdout,
        "has_changes": len(proc.stdout) > 0,
        "duration_ms": 0
    }


def lint_run(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run linter on the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - linter: Linter to use (pylint, eslint, etc.)
            - paths: Paths to lint
    
    Returns:
        Tool result with lint output
    """
    worktree_path = args.get("worktree_path", ".")
    linter = args.get("linter", "pylint")
    paths = args.get("paths", ["."])
    
    cmd = [linter] + paths
    
    proc = subprocess.run(
        cmd,
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=120
    )
    
    # Linters often return non-zero for style issues
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
        "duration_ms": 0
    }


def typecheck_run(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run type checker on the worktree.
    
    Args:
        args: Tool arguments
            - worktree_path: Path to worktree
            - checker: Type checker (mypy, tsc, etc.)
            - paths: Paths to check
    
    Returns:
        Tool result with type check output
    """
    worktree_path = args.get("worktree_path", ".")
    checker = args.get("checker", "mypy")
    paths = args.get("paths", ["."])
    
    cmd = [checker] + paths
    
    proc = subprocess.run(
        cmd,
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=120
    )
    
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
        "duration_ms": 0
    }


# Tool registry
TOOL_MAP = {
    "test.run": run_tests,
    "file.read": read_file,
    "file.read_batch": read_file_batch,
    "search.text": search_text,
    "git.status": git_status,
    "git.diff": git_diff,
    "lint.run": lint_run,
    "typecheck.run": typecheck_run,
}


def get_tool_names() -> List[str]:
    """Get list of available tool names.
    
    Returns:
        List of tool names
    """
    return list(TOOL_MAP.keys())


def get_tool(tool_name: str):
    """Get a tool by name.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Tool function or None
    """
    return TOOL_MAP.get(tool_name)
