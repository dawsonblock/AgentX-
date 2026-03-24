"""Tool Bridge for GSD Wrapper

Mediates tool requests from the worker through the runtime executor.
"""

from typing import Dict, Any, Optional, List
from uuid import uuid4

from .contracts import ToolRequest, ToolResponse


class ToolBridge:
    """Bridge for executing tools through the runtime.
    
    The worker sees a narrow tool surface:
    - read_file
    - read_files
    - write_file
    - search_repo
    - run_tests
    - run_lint
    - run_typecheck
    - get_git_status
    - get_diff
    - get_git_diff
    
    Each tool call goes through runtime executor, never directly to filesystem.
    """

    def __init__(self, run_id: str, executor_broker, worktree_path: str = None):
        """Initialize tool bridge.
        
        Args:
            run_id: Run ID
            executor_broker: Runtime executor broker
            worktree_path: Path to the worktree
        """
        self.run_id = run_id
        self.executor = executor_broker
        self.worktree_path = worktree_path
        self.request_log: list = []

    def read_file(self, path: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read a file.
        
        Args:
            path: File path (relative to worktree)
            limit: Optional line limit
            
        Returns:
            File content result
        """
        return self._execute_tool("file.read", {
            "worktree_path": self.worktree_path,
            "path": path,
            "limit": limit
        })

    def read_files(self, paths: List[str], limit: Optional[int] = None) -> Dict[str, Any]:
        """Read multiple files.
        
        Args:
            paths: List of file paths
            limit: Optional line limit per file
            
        Returns:
            Batch file content result
        """
        return self._execute_tool("file.read_batch", {
            "worktree_path": self.worktree_path,
            "paths": paths,
            "limit": limit
        })

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write a file.
        
        Args:
            path: File path (relative to worktree)
            content: Content to write
            
        Returns:
            Write result
        """
        return self._execute_tool("file.write", {
            "worktree_path": self.worktree_path,
            "path": path,
            "content": content
        })

    def search_repo(self, query: str, path_filter: Optional[str] = None) -> Dict[str, Any]:
        """Search for text in the repository.
        
        Args:
            query: Search query
            path_filter: Optional path glob filter
            
        Returns:
            Search results
        """
        return self._execute_tool("search.text", {
            "worktree_path": self.worktree_path,
            "query": query,
            "path_filter": path_filter
        })

    def run_tests(self, test_path: Optional[str] = None, runner: str = "pytest") -> Dict[str, Any]:
        """Run tests.
        
        Args:
            test_path: Optional specific test path
            runner: Test runner to use
            
        Returns:
            Test results
        """
        return self._execute_tool("test.run", {
            "worktree_path": self.worktree_path,
            "test_path": test_path,
            "runner": runner
        })

    def run_lint(self, paths: Optional[List[str]] = None, linter: str = "pylint") -> Dict[str, Any]:
        """Run linter.
        
        Args:
            paths: Paths to lint
            linter: Linter to use
            
        Returns:
            Lint results
        """
        return self._execute_tool("lint.run", {
            "worktree_path": self.worktree_path,
            "paths": paths or ["."],
            "linter": linter
        })

    def run_typecheck(self, paths: Optional[List[str]] = None, checker: str = "mypy") -> Dict[str, Any]:
        """Run type checker.
        
        Args:
            paths: Paths to check
            checker: Type checker to use
            
        Returns:
            Type check results
        """
        return self._execute_tool("typecheck.run", {
            "worktree_path": self.worktree_path,
            "paths": paths or ["."],
            "checker": checker
        })

    def get_git_status(self) -> Dict[str, Any]:
        """Get git status.
        
        Returns:
            Git status
        """
        return self._execute_tool("git.status", {
            "worktree_path": self.worktree_path
        })

    def get_diff(self, staged: bool = False) -> Dict[str, Any]:
        """Get git diff.
        
        Args:
            staged: Show staged changes
            
        Returns:
            Git diff
        """
        return self._execute_tool("git.diff", {
            "worktree_path": self.worktree_path,
            "staged": staged
        })

    def get_git_diff(self) -> str:
        """Get git diff as string.
        
        Returns:
            Diff text or empty string if no changes
        """
        result = self._execute_tool("git.diff", {
            "worktree_path": self.worktree_path
        })
        return result.get("diff", "")

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool through the executor.
        
        Args:
            tool_name: Tool name
            args: Tool arguments
            
        Returns:
            Tool result
        """
        request_id = str(uuid4())
        
        # Log request
        self.request_log.append({
            "request_id": request_id,
            "tool_name": tool_name,
            "args": {k: v for k, v in args.items() if k != "worktree_path"}  # Don't log path
        })
        
        # Execute through runtime executor
        result = self.executor.execute(
            tool_name=tool_name,
            args=args,
            actor_kind="worker",
            actor_id=f"gsd-{self.run_id}"
        )
        
        return result

    def get_request_log(self) -> List[Dict[str, Any]]:
        """Get log of all tool requests.
        
        Returns:
            Request log
        """
        return self.request_log.copy()
