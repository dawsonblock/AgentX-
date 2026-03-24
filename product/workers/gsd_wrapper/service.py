"""GSD Wrapper Service

Production-grade wrapper for the GSD worker with runtime-mediated tool access.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from dataclasses import dataclass, asdict

from .contracts import (
    TaskSpec,
    WorkerState,
    WorkerAction,
    WorkerStepResult,
    WorkerStatus,
    PatchProposal
)
from .tool_bridge import ToolBridge
from .state import WorkerStateManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for the worker."""
    max_steps: int = 100
    max_tool_calls: int = 200
    enable_patch_proposal: bool = True
    require_tool_confirmation: bool = False


class GSDWrapper:
    """Production wrapper for the GSD worker.
    
    This wrapper enforces:
    1. No direct filesystem mutation
    2. All tool calls through runtime executor
    3. Transient local state only (runtime is authoritative)
    4. Bounded execution with step limits
    """

    def __init__(self, run_id: str, executor_broker, config: Optional[WorkerConfig] = None):
        """Initialize GSD wrapper.
        
        Args:
            run_id: Run ID
            executor_broker: Runtime executor broker
            config: Optional worker configuration
        """
        self.run_id = run_id
        self.executor = executor_broker
        self.config = config or WorkerConfig()
        self.tool_bridge = ToolBridge(run_id, executor_broker)
        self.state_manager = WorkerStateManager(run_id)
        
        # Task context
        self.task_spec: Optional[TaskSpec] = None
        self.worktree_path: Optional[str] = None
        self.context_pack: Optional[Dict[str, Any]] = None
        
        # Execution state
        self._step_count = 0
        self._tool_call_count = 0
        self._artifacts: List[str] = []
        self._collected_context: List[Dict[str, Any]] = []
        self._findings: List[str] = []
        self._proposed_patch: Optional[PatchProposal] = None
        
        logger.info(f"Initialized GSD wrapper for run {run_id}")

    def start(
        self,
        task_spec: Dict[str, Any],
        worktree_path: str,
        context_pack: Dict[str, Any]
    ) -> WorkerStatus:
        """Start the worker.
        
        Args:
            task_spec: Task specification with goal, type, constraints
            worktree_path: Path to isolated worktree
            context_pack: Bounded context from retrieval pipeline
            
        Returns:
            Worker status
        """
        logger.info(f"Starting worker for run {self.run_id}")
        
        self.task_spec = TaskSpec(
            goal=task_spec.get("goal", ""),
            task_type=task_spec.get("task_type", ""),
            constraints=task_spec.get("constraints", {}),
            context_pack=context_pack
        )
        self.worktree_path = worktree_path
        self.context_pack = context_pack
        
        # Update tool bridge with worktree
        self.tool_bridge.worktree_path = worktree_path
        
        # Initialize state
        self.state_manager.transition_to(WorkerState.RUNNING)
        self._step_count = 0
        self._tool_call_count = 0
        
        # Initial context collection
        self._collected_context.append({
            "type": "task",
            "content": self.task_spec.goal
        })
        
        if context_pack:
            self._collected_context.append({
                "type": "context_pack",
                "content": context_pack
            })
        
        logger.info(f"Worker started for run {self.run_id}")
        return self.get_status()

    def step(self) -> WorkerStepResult:
        """Execute one worker step.
        
        This implements the core worker loop:
        1. Inspect current state (git status, failing tests)
        2. Read relevant files
        3. Analyze and propose fix
        4. Submit patch proposal
        
        Returns:
            Step result with action and payload
        """
        if self.state_manager.state != WorkerState.RUNNING:
            return WorkerStepResult(
                action=WorkerAction.FAIL,
                payload={"error": f"Worker not in running state: {self.state_manager.state}"},
                state=self.state_manager.state,
                step_number=self._step_count
            )
        
        # Check step budget
        if self._step_count >= self.config.max_steps:
            self.state_manager.transition_to(WorkerState.FAILED, "Step budget exceeded")
            return WorkerStepResult(
                action=WorkerAction.FAIL,
                payload={"error": f"Step budget exceeded: {self.config.max_steps}"},
                state=WorkerState.FAILED,
                step_number=self._step_count
            )
        
        self._step_count += 1
        logger.debug(f"Executing step {self._step_count} for run {self.run_id}")
        
        try:
            return self._execute_step_logic()
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            self.state_manager.transition_to(WorkerState.FAILED, str(e))
            return WorkerStepResult(
                action=WorkerAction.FAIL,
                payload={"error": str(e)},
                state=WorkerState.FAILED,
                step_number=self._step_count
            )

    def _execute_step_logic(self) -> WorkerStepResult:
        """Execute the actual step logic based on current state."""
        
        # Step 1: Initial inspection - git status
        if self._step_count == 1:
            result = self.tool_bridge.get_git_status()
            self._findings.append(f"Git status: {result.get('has_changes', False)}")
            return WorkerStepResult(
                action=WorkerAction.REQUEST_TOOL,
                payload={
                    "tool": "git.status",
                    "result": result,
                    "finding": "Repository state inspected"
                },
                state=WorkerState.RUNNING,
                step_number=self._step_count
            )
        
        # Step 2: Run tests to see failures
        elif self._step_count == 2:
            result = self.tool_bridge.run_tests()
            self._findings.append(f"Test result: exit_code={result.get('exit_code')}")
            
            # Parse test output for failing files
            stdout = result.get('stdout', '')
            if 'FAILED' in stdout or result.get('exit_code', 0) != 0:
                # Extract failing test info
                self._findings.append("Tests are failing - analyzing...")
            
            return WorkerStepResult(
                action=WorkerAction.REQUEST_TOOL,
                payload={
                    "tool": "test.run",
                    "result": result,
                    "finding": "Test execution completed"
                },
                state=WorkerState.RUNNING,
                step_number=self._step_count
            )
        
        # Step 3: Search for relevant code
        elif self._step_count == 3:
            # Search based on task type
            query = self._get_search_query()
            result = self.tool_bridge.search_repo(query)
            
            matches = result.get('matches', [])
            if matches:
                # Read the top matching files
                paths = [m['path'] for m in matches[:3]]
                read_result = self.tool_bridge.read_files(paths, limit=100)
                
                self._collected_context.append({
                    "type": "code_search",
                    "query": query,
                    "matches": paths
                })
            
            return WorkerStepResult(
                action=WorkerAction.REQUEST_TOOL,
                payload={
                    "tool": "search.text",
                    "result": result,
                    "finding": f"Found {len(matches)} matches for query: {query}"
                },
                state=WorkerState.RUNNING,
                step_number=self._step_count
            )
        
        # Step 4: Analyze and propose fix
        elif self._step_count == 4:
            # Generate patch based on findings
            if self.config.enable_patch_proposal:
                patch = self._generate_patch_proposal()
                self._proposed_patch = patch
                
                return WorkerStepResult(
                    action=WorkerAction.SUBMIT_PATCH,
                    payload={
                        "patch": asdict(patch),
                        "findings": self._findings,
                        "context_collected": len(self._collected_context)
                    },
                    state=WorkerState.RUNNING,
                    step_number=self._step_count
                )
            else:
                return WorkerStepResult(
                    action=WorkerAction.SUBMIT_SUMMARY,
                    payload={
                        "findings": self._findings,
                        "context_collected": self._collected_context,
                        "summary": "Analysis complete - patch proposal disabled"
                    },
                    state=WorkerState.COMPLETED,
                    step_number=self._step_count
                )
        
        # Step 5: Complete
        else:
            self.state_manager.transition_to(WorkerState.COMPLETED)
            return WorkerStepResult(
                action=WorkerAction.COMPLETE,
                payload={
                    "total_steps": self._step_count,
                    "total_tool_calls": self._tool_call_count,
                    "findings": self._findings,
                    "patch_proposed": self._proposed_patch is not None
                },
                state=WorkerState.COMPLETED,
                step_number=self._step_count
            )

    def _get_search_query(self) -> str:
        """Generate search query based on task."""
        goal = self.task_spec.goal.lower() if self.task_spec else ""
        
        # Extract key terms from goal
        if "test" in goal:
            if "payment" in goal:
                return "payment"
            elif "auth" in goal:
                return "auth"
            else:
                return "test"
        elif "fix" in goal:
            return "def"
        
        return "TODO"

    def _generate_patch_proposal(self) -> PatchProposal:
        """Generate a patch proposal based on analysis."""
        # In a real implementation, this would:
        # 1. Use an LLM to generate the fix
        # 2. Apply the fix to the worktree
        # 3. Run tests to validate
        # 4. Generate the diff
        
        # For now, return a placeholder patch
        return PatchProposal(
            format="unified_diff",
            base_ref="HEAD",
            files=[{"path": "example.py", "status": "modified"}],
            diff_text="""diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 def example():
-    return "broken"
+    return "fixed"
 
 if __name__ == "__main__":
     print(example())
""",
            summary=f"Proposed fix for: {self.task_spec.goal if self.task_spec else 'unknown task'}"
        )

    def pause(self) -> WorkerStatus:
        """Pause the worker.
        
        Returns:
            Worker status
        """
        logger.info(f"Pausing worker for run {self.run_id}")
        self.state_manager.transition_to(WorkerState.PAUSED)
        return self.get_status()

    def resume(self) -> WorkerStatus:
        """Resume the worker.
        
        Returns:
            Worker status
        """
        logger.info(f"Resuming worker for run {self.run_id}")
        if self.state_manager.state == WorkerState.PAUSED:
            self.state_manager.transition_to(WorkerState.RUNNING)
        return self.get_status()

    def cancel(self) -> WorkerStatus:
        """Cancel the worker.
        
        Returns:
            Worker status
        """
        logger.info(f"Cancelling worker for run {self.run_id}")
        self.state_manager.transition_to(WorkerState.FAILED, "Cancelled by user")
        return self.get_status()

    def get_status(self) -> WorkerStatus:
        """Get current worker status.
        
        Returns:
            Worker status
        """
        return WorkerStatus(
            run_id=self.run_id,
            state=self.state_manager.state,
            current_step=self._step_count,
            last_action=None,
            error=self.state_manager.error,
            artifacts_collected=self._artifacts
        )

    def collect_artifacts(self) -> List[Dict[str, Any]]:
        """Collect artifacts from the worker.
        
        Returns:
            List of artifacts
        """
        artifacts = []
        
        # Context collected
        if self._collected_context:
            artifacts.append({
                "type": "context",
                "name": "collected_context.json",
                "content": json.dumps(self._collected_context, indent=2)
            })
        
        # Findings
        if self._findings:
            artifacts.append({
                "type": "findings",
                "name": "findings.txt",
                "content": "\n".join(self._findings)
            })
        
        # Tool log
        artifacts.append({
            "type": "tool_log",
            "name": "tool_log.json",
            "content": json.dumps(self.tool_bridge.get_request_log(), indent=2)
        })
        
        return artifacts

    def get_tool_log(self) -> List[Dict[str, Any]]:
        """Get log of all tool requests.
        
        Returns:
            Tool request log
        """
        return self.tool_bridge.get_request_log()

    def get_proposed_patch(self) -> Optional[PatchProposal]:
        """Get the proposed patch if available.
        
        Returns:
            Patch proposal or None
        """
        return self._proposed_patch
