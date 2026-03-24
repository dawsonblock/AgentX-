"""Executor broker - mediates all tool execution.

This is the hard boundary. All side effects go through here.
"""

from uuid import UUID
from typing import Dict, Any, Optional
import time

from .tools import get_tool, ToolError
from ..policy.engine import PolicyEngine
from ..events.store import EventStore


class ExecutorBroker:
    """Broker for executing tools.
    
    The broker:
    1. Validates tool requests through policy
    2. Emits start event
    3. Executes the tool
    4. Emits finish event
    5. Returns structured result
    """

    def __init__(
        self,
        policy_engine: PolicyEngine,
        event_store: EventStore,
        run_id: UUID
    ):
        """Initialize executor broker.
        
        Args:
            policy_engine: Policy engine for validation
            event_store: Event store for logging
            run_id: Run ID being executed
        """
        self.policy_engine = policy_engine
        self.event_store = event_store
        self.run_id = run_id

    def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        actor_kind: str = "worker",
        actor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a tool through the broker.
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            actor_kind: Kind of actor requesting execution
            actor_id: Actor identifier
            
        Returns:
            Tool execution result
        """
        # Check policy
        policy_result = self.policy_engine.check_tool(tool_name, args)
        
        if not policy_result.allowed:
            # Emit denied event
            self.event_store.append(
                run_id=self.run_id,
                event_type="ToolDenied",
                payload={
                    "tool": tool_name,
                    "args": args,
                    "reason": policy_result.reason
                },
                actor_kind=actor_kind,
                actor_id=actor_id
            )
            
            return {
                "tool_name": tool_name,
                "exit_code": -1,
                "error": policy_result.reason,
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
                "files_touched": [],
                "artifacts_produced": []
            }

        # Get the tool
        tool = get_tool(tool_name)
        if not tool:
            return {
                "tool_name": tool_name,
                "exit_code": -1,
                "error": f"Unknown tool: {tool_name}",
                "stdout": "",
                "stderr": "",
                "duration_ms": 0
            }

        # Emit started event
        self.event_store.append(
            run_id=self.run_id,
            event_type="ToolStarted",
            payload={
                "tool": tool_name,
                "args": self._sanitize_args(args)
            },
            actor_kind=actor_kind,
            actor_id=actor_id
        )

        # Execute the tool
        start_time = time.time()
        
        try:
            result = tool(args)
            exit_code = result.get("exit_code", 0)
            error = None
        except ToolError as e:
            result = {
                "exit_code": e.exit_code,
                "stderr": e.stderr,
                "stdout": ""
            }
            exit_code = e.exit_code
            error = str(e)
        except Exception as e:
            result = {
                "exit_code": -1,
                "stderr": str(e),
                "stdout": ""
            }
            exit_code = -1
            error = str(e)
        
        duration_ms = int((time.time() - start_time) * 1000)

        # Record execution in policy engine
        self.policy_engine.record_execution(tool_name)

        # Build result
        tool_result = {
            "tool_name": tool_name,
            "exit_code": exit_code,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "duration_ms": duration_ms,
            "files_touched": result.get("files_touched", []),
            "artifacts_produced": result.get("artifacts_produced", [])
        }
        
        if error:
            tool_result["error"] = error

        # Emit finished event
        self.event_store.append(
            run_id=self.run_id,
            event_type="ToolFinished",
            payload={
                "tool": tool_name,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "error": error
            },
            actor_kind=actor_kind,
            actor_id=actor_id
        )

        return tool_result

    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize args for logging (remove sensitive data).
        
        Args:
            args: Raw arguments
            
        Returns:
            Sanitized arguments
        """
        # For now, return args as-is
        # Can be extended to redact sensitive fields
        return args

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics from policy engine.
        
        Returns:
            Usage statistics
        """
        return self.policy_engine.get_usage_stats()
