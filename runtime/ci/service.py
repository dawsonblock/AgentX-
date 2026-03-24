"""CI Service - runs quality checks on patches before application.

This service executes CI gates:
- Lint checks
- Type checks  
- Test execution
- Secrets scanning

Results are stored and used to determine if a patch can be promoted.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..policy import SecureSubprocess, run_secure, scan_patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CIGateStatus(Enum):
    """Status of a CI gate."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CIGateResult:
    """Result of a single CI gate."""
    name: str
    status: CIGateStatus
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class CIResult:
    """Overall CI result for a patch."""
    patch_id: str
    overall_status: CIGateStatus
    gates: List[CIGateResult]
    summary: str


class CIService:
    """Service for running CI checks on patches."""

    # Default gates to run
    DEFAULT_GATES = ["secrets", "lint", "typecheck", "test"]

    def __init__(self):
        """Initialize CI service."""
        self.gate_configs = {
            "secrets": {
                "description": "Scan for secrets and sensitive data",
                "timeout": 30,
            },
            "lint": {
                "command": ["flake8"],  # Use flake8 instead of pylint (faster)
                "timeout": 120,
                "files": ["."],
            },
            "typecheck": {
                "command": ["mypy"],
                "timeout": 120,
                "files": ["."],
            },
            "test": {
                "command": ["pytest"],
                "timeout": 300,
                "files": [],  # Will run all tests
            },
            "build": {
                "command": ["python", "-m", "py_compile"],
                "timeout": 60,
                "files": ["."],
            },
            "security": {
                "command": ["bandit", "-r"],
                "timeout": 120,
                "files": ["."],
            },
        }

    def run_ci_checks(
        self,
        worktree_path: str,
        patch_id: str,
        gates: Optional[List[str]] = None,
        repo_type: str = "python",
        diff_text: Optional[str] = None
    ) -> CIResult:
        """Run CI checks on a worktree.
        
        Args:
            worktree_path: Path to the worktree
            patch_id: Patch ID being checked
            gates: List of gates to run (default: all)
            repo_type: Repository type for command selection
            diff_text: Optional diff text for secrets scanning
            
        Returns:
            CIResult with overall status
        """
        gates = gates or self.DEFAULT_GATES
        gate_results: List[CIGateResult] = []
        
        logger.info(f"Running CI checks for patch {patch_id} in {worktree_path}")
        
        # First, always run secrets scan if diff is provided
        if diff_text and "secrets" in gates:
            logger.info("Running secrets scan")
            result = self._run_secrets_gate(diff_text)
            gate_results.append(result)
            gates = [g for g in gates if g != "secrets"]  # Remove from remaining
            
            # If secrets found, stop immediately
            if result.status == CIGateStatus.FAILED:
                logger.error(f"CRITICAL: Secrets detected in patch {patch_id}")
                return CIResult(
                    patch_id=patch_id,
                    overall_status=CIGateStatus.FAILED,
                    gates=gate_results,
                    summary="CRITICAL: Secrets detected - patch blocked"
                )
        
        # Run remaining gates using secure subprocess
        with SecureSubprocess(worktree_path=worktree_path) as executor:
            for gate_name in gates:
                logger.info(f"Running gate: {gate_name}")
                result = self._run_gate(gate_name, worktree_path, repo_type, executor)
                gate_results.append(result)
                
                # If a gate fails, we can stop early
                if result.status == CIGateStatus.FAILED:
                    logger.warning(f"Gate {gate_name} failed, stopping CI")
                    break
        
        # Determine overall status
        overall_status = CIGateStatus.PASSED
        for result in gate_results:
            if result.status == CIGateStatus.FAILED:
                overall_status = CIGateStatus.FAILED
                break
            elif result.status == CIGateStatus.SKIPPED:
                overall_status = CIGateStatus.SKIPPED
        
        summary = self._generate_summary(gate_results)
        
        return CIResult(
            patch_id=patch_id,
            overall_status=overall_status,
            gates=gate_results,
            summary=summary
        )

    def _run_secrets_gate(self, diff_text: str) -> CIGateResult:
        """Run secrets scanning gate.
        
        Args:
            diff_text: Git diff to scan
            
        Returns:
            Gate result
        """
        import time
        start_time = time.time()
        
        try:
            matches, should_block, report = scan_patch(diff_text)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if should_block:
                return CIGateResult(
                    name="secrets",
                    status=CIGateStatus.FAILED,
                    exit_code=1,
                    stdout=report,
                    stderr=f"CRITICAL: {len(matches)} secret(s) detected in patch",
                    duration_ms=duration_ms
                )
            elif matches:
                # Non-critical secrets found (warnings)
                return CIGateResult(
                    name="secrets",
                    status=CIGateStatus.PASSED,  # Don't block for warnings
                    exit_code=0,
                    stdout=report,
                    stderr=f"WARNING: {len(matches)} potential secret(s) detected",
                    duration_ms=duration_ms
                )
            else:
                return CIGateResult(
                    name="secrets",
                    status=CIGateStatus.PASSED,
                    exit_code=0,
                    stdout=report,
                    stderr="",
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Secrets scan failed: {e}")
            return CIGateResult(
                name="secrets",
                status=CIGateStatus.SKIPPED,
                exit_code=-1,
                stdout="",
                stderr=f"Secrets scan error: {e}",
                duration_ms=duration_ms
            )

    def _run_gate(
        self,
        gate_name: str,
        worktree_path: str,
        repo_type: str,
        executor: SecureSubprocess
    ) -> CIGateResult:
        """Run a single CI gate using secure subprocess.
        
        Args:
            gate_name: Name of the gate
            worktree_path: Path to worktree
            repo_type: Repository type
            executor: Secure subprocess executor
            
        Returns:
            Gate result
        """
        import time
        
        # Get gate configuration
        config = self._get_gate_config(gate_name, repo_type)
        
        if not config:
            return CIGateResult(
                name=gate_name,
                status=CIGateStatus.SKIPPED,
                exit_code=0,
                stdout="",
                stderr="Gate not configured for this repo type",
                duration_ms=0
            )
        
        # Build command
        cmd = config["command"] + config.get("files", ["."])
        timeout = config.get("timeout", 120)
        
        start_time = time.time()
        
        try:
            # Use secure subprocess
            result = executor.run(cmd, timeout=timeout)
            
            duration_ms = result.duration_ms
            
            # Determine status
            if result.timed_out:
                status = CIGateStatus.FAILED
                stderr = f"Gate timed out after {timeout}s\n{result.stderr}"
            elif result.error_message:
                status = CIGateStatus.FAILED
                stderr = f"Execution error: {result.error_message}\n{result.stderr}"
            else:
                # Tool-specific exit code interpretation
                status = self._interpret_exit_code(gate_name, result.returncode)
                stderr = result.stderr
            
            return CIGateResult(
                name=gate_name,
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout[-10000:] if len(result.stdout) > 10000 else result.stdout,
                stderr=stderr[-5000:] if len(stderr) > 5000 else stderr,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gate {gate_name} execution error: {e}")
            return CIGateResult(
                name=gate_name,
                status=CIGateStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {e}",
                duration_ms=duration_ms
            )

    def _interpret_exit_code(self, gate_name: str, exit_code: int) -> CIGateStatus:
        """Interpret exit code based on gate type."""
        if exit_code < 0:
            # Negative exit code means signal/termination
            return CIGateStatus.FAILED
        
        if gate_name == "lint":
            # flake8: 0 = no issues, 1 = errors found
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED
        elif gate_name == "typecheck":
            # mypy: 0 = success, 1 = errors
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED
        elif gate_name == "test":
            # pytest: 0 = all passed, 1-5 = various failure modes
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED
        elif gate_name == "build":
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED
        elif gate_name == "security":
            # bandit: 0 = no issues, 1 = low, 2 = medium, 3 = high
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED
        else:
            return CIGateStatus.PASSED if exit_code == 0 else CIGateStatus.FAILED

    def _get_gate_config(
        self,
        gate_name: str,
        repo_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a CI gate based on repo type."""
        # Get base config
        config = self.gate_configs.get(gate_name)
        if not config:
            return None
        
        # Skip if no command (e.g., secrets gate handled separately)
        if "command" not in config:
            return None
        
        # Adjust commands based on repo type
        if repo_type == "python":
            if gate_name == "lint":
                return {"command": ["flake8"], "timeout": 120, "files": ["."]}
            elif gate_name == "typecheck":
                return {"command": ["mypy"], "timeout": 120, "files": ["."]}
            elif gate_name == "test":
                return {"command": ["pytest"], "timeout": 300, "files": []}
            elif gate_name == "build":
                return {"command": ["python", "-m", "py_compile"], "timeout": 60, "files": ["."]}
            elif gate_name == "security":
                return {"command": ["bandit", "-r"], "timeout": 120, "files": ["."]}
                
        elif repo_type == "node":
            if gate_name == "lint":
                return {"command": ["eslint"], "timeout": 120, "files": ["."]}
            elif gate_name == "typecheck":
                return {"command": ["npx", "tsc", "--noEmit"], "timeout": 120, "files": []}
            elif gate_name == "test":
                return {"command": ["npm", "test"], "timeout": 300, "files": []}
            elif gate_name == "build":
                return {"command": ["npm", "run", "build"], "timeout": 180, "files": []}
            elif gate_name == "security":
                return {"command": ["npm", "audit"], "timeout": 120, "files": []}
                
        elif repo_type == "go":
            if gate_name == "lint":
                return {"command": ["gofmt", "-l"], "timeout": 60, "files": ["."]}
            elif gate_name == "typecheck":
                return {"command": ["go", "vet"], "timeout": 120, "files": ["."]}
            elif gate_name == "test":
                return {"command": ["go", "test", "./..."], "timeout": 300, "files": []}
            elif gate_name == "build":
                return {"command": ["go", "build", "./..."], "timeout": 180, "files": []}
            elif gate_name == "security":
                return {"command": ["gosec", "./..."], "timeout": 120, "files": []}
                
        elif repo_type == "rust":
            if gate_name == "lint":
                return {"command": ["cargo", "fmt", "--", "--check"], "timeout": 120, "files": []}
            elif gate_name == "typecheck":
                return {"command": ["cargo", "check"], "timeout": 180, "files": []}
            elif gate_name == "test":
                return {"command": ["cargo", "test"], "timeout": 300, "files": []}
            elif gate_name == "build":
                return {"command": ["cargo", "build"], "timeout": 300, "files": []}
            elif gate_name == "security":
                return {"command": ["cargo", "audit"], "timeout": 120, "files": []}
        
        # Default to Python commands if repo type not recognized
        return config if repo_type == "python" else None

    def _generate_summary(self, gate_results: List[CIGateResult]) -> str:
        """Generate a summary of CI results."""
        passed = sum(1 for r in gate_results if r.status == CIGateStatus.PASSED)
        failed = sum(1 for r in gate_results if r.status == CIGateStatus.FAILED)
        skipped = sum(1 for r in gate_results if r.status == CIGateStatus.SKIPPED)
        
        total_time = sum(r.duration_ms for r in gate_results)
        
        if failed > 0:
            status_str = "FAILED"
        elif skipped > 0 and passed == 0:
            status_str = "SKIPPED"
        else:
            status_str = "PASSED"
        
        return f"{status_str}: {passed} passed, {failed} failed, {skipped} skipped ({total_time}ms)"

    def detect_repo_type(self, worktree_path: str) -> str:
        """Detect repository type from files present."""
        import os
        
        files = os.listdir(worktree_path)
        
        if "Cargo.toml" in files:
            return "rust"
        elif "go.mod" in files:
            return "go"
        elif "package.json" in files:
            return "node"
        elif any(f.endswith(".py") for f in files):
            return "python"
        elif "requirements.txt" in files:
            return "python"
        elif "setup.py" in files:
            return "python"
        elif "pyproject.toml" in files:
            return "python"
        
        return "python"  # Default


# Global service instance
_ci_service: Optional[CIService] = None


def get_service() -> CIService:
    """Get the global CI service instance."""
    global _ci_service
    if _ci_service is None:
        _ci_service = CIService()
    return _ci_service
