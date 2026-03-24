"""Policy engine - enforces execution boundaries and constraints."""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class PolicyResult:
    """Result of a policy check."""
    allowed: bool
    reason: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunConstraints:
    """Constraints for a run.
    
    These are set at run creation and enforced throughout execution.
    """
    network_allowed: bool = False
    approval_required_for_patch_apply: bool = True
    max_steps: int = 100
    max_duration_seconds: int = 3600
    writable_paths: List[str] = field(default_factory=list)
    allowed_tools: Optional[Set[str]] = None
    blocked_tools: Set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunConstraints":
        """Create constraints from dictionary."""
        return cls(
            network_allowed=data.get("network", False),
            approval_required_for_patch_apply=data.get("approval_required_for_patch_apply", True),
            max_steps=data.get("max_steps", 100),
            max_duration_seconds=data.get("max_duration_seconds", 3600),
            writable_paths=data.get("writable_paths", []),
            allowed_tools=set(data["allowed_tools"]) if "allowed_tools" in data else None,
            blocked_tools=set(data.get("blocked_tools", []))
        )


class PolicyEngine:
    """Policy engine for enforcing execution boundaries.
    
    The policy engine is the hard boundary between the worker and the system.
    Every tool request goes through the policy engine.
    """

    # Default allowed tools for v1
    DEFAULT_ALLOWED_TOOLS: Set[str] = {
        # Repository inspection
        "repo.read_tree",
        "file.read",
        "file.read_batch",
        
        # Search
        "search.text",
        "search.symbol",
        
        # Git operations (read-only)
        "git.status",
        "git.diff",
        "git.log",
        "git.show",
        
        # Testing and validation
        "test.run",
        "lint.run",
        "typecheck.run",
        
        # Patch operations
        "patch.apply_candidate",
        "patch.validate",
        
        # Artifact collection
        "artifact.collect",
        
        # Completion
        "worker.submit_patch",
        "worker.complete",
    }

    # Tools that require explicit approval
    APPROVAL_REQUIRED_TOOLS: Set[str] = {
        "patch.apply_candidate",
    }

    def __init__(self, constraints: Optional[RunConstraints] = None):
        """Initialize policy engine.
        
        Args:
            constraints: Run constraints
        """
        self.constraints = constraints or RunConstraints()
        self.step_count = 0
        self.tool_usage: Dict[str, int] = {}

    def check_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        run_state: Optional[str] = None
    ) -> PolicyResult:
        """Check if a tool execution is allowed.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            run_state: Current run state
            
        Returns:
            Policy result
        """
        # Check step budget
        if self.step_count >= self.constraints.max_steps:
            return PolicyResult(
                allowed=False,
                reason=f"Step budget exceeded: {self.constraints.max_steps}"
            )

        # Check if tool is explicitly blocked
        if tool_name in self.constraints.blocked_tools:
            return PolicyResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is blocked"
            )

        # Check if tool is in allowed list
        allowed_tools = self.constraints.allowed_tools or self.DEFAULT_ALLOWED_TOOLS
        if tool_name not in allowed_tools:
            return PolicyResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is not in allowed set"
            )

        # Check approval requirements
        if tool_name in self.APPROVAL_REQUIRED_TOOLS:
            if self.constraints.approval_required_for_patch_apply:
                return PolicyResult(
                    allowed=False,
                    reason=f"Tool '{tool_name}' requires approval before execution"
                )

        # Check network access
        if not self.constraints.network_allowed:
            if self._requires_network(tool_name, args):
                return PolicyResult(
                    allowed=False,
                    reason="Network access is not allowed for this run"
                )

        # Check writable paths
        if "path" in args:
            path = args["path"]
            if not self._is_path_allowed(path):
                return PolicyResult(
                    allowed=False,
                    reason=f"Path '{path}' is not in writable allowlist"
                )

        return PolicyResult(allowed=True)

    def record_execution(self, tool_name: str) -> None:
        """Record a tool execution for tracking.
        
        Args:
            tool_name: Name of the executed tool
        """
        self.step_count += 1
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics.
        
        Returns:
            Usage statistics
        """
        return {
            "step_count": self.step_count,
            "step_budget": self.constraints.max_steps,
            "tool_usage": self.tool_usage
        }

    def _requires_network(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Check if a tool requires network access.
        
        Args:
            tool_name: Tool name
            args: Tool arguments
            
        Returns:
            True if network is required
        """
        # Currently no tools require network in v1
        # This can be extended as needed
        network_tools = {"network.fetch", "git.clone", "git.push", "git.pull"}
        return tool_name in network_tools

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is in the writable allowlist.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is allowed
        """
        if not self.constraints.writable_paths:
            # No restrictions
            return True
        
        # Check if path starts with any allowed prefix
        for allowed in self.constraints.writable_paths:
            if path.startswith(allowed):
                return True
        
        return False

    @classmethod
    def from_run_constraints(cls, constraints_json: Dict[str, Any]) -> "PolicyEngine":
        """Create policy engine from run constraints.
        
        Args:
            constraints_json: Constraints from run record
            
        Returns:
            Policy engine
        """
        constraints = RunConstraints.from_dict(constraints_json)
        return cls(constraints)
