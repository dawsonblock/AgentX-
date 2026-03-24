"""Secure subprocess wrapper with timeout and resource limits.

This module provides a secure wrapper around subprocess execution
that enforces:
- Command allowlisting
- Timeout enforcement
- Resource limits (memory, CPU)
- Output size limits
- Path sandboxing
"""

import subprocess
import signal
import resource
import os
import sys
import threading
import time
import tempfile
import shutil
from typing import List, Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging

from .security import SecurityEnforcer, SecurityPolicy, get_security_enforcer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SubprocessResult:
    """Result of a subprocess execution."""
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    memory_exceeded: bool = False
    output_truncated: bool = False
    error_message: Optional[str] = None


class ResourceLimiter:
    """Sets resource limits for child processes."""
    
    def __init__(self, max_memory_mb: int, max_cpu_time: int):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time = max_cpu_time
    
    def __call__(self):
        """Called in child process before exec."""
        try:
            # Set memory limit (soft, hard)
            max_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
            
            # Set CPU time limit (soft, hard)
            resource.setrlimit(resource.RLIMIT_CPU, (self.max_cpu_time, self.max_cpu_time + 5))
            
            # Set maximum number of open files
            resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 2048))
            
            # Set maximum process count (prevent fork bombs)
            resource.setrlimit(resource.RLIMIT_NPROC, (512, 1024))
            
            # Set maximum file size (prevent huge output files)
            max_file_size = 100 * 1024 * 1024  # 100MB
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size, max_file_size))
            
        except Exception as e:
            # Log but don't fail - limits are best-effort on some systems
            logger.warning(f"Could not set all resource limits: {e}")


class SecureSubprocess:
    """Secure subprocess executor with policy enforcement."""
    
    def __init__(self, 
                 enforcer: Optional[SecurityEnforcer] = None,
                 worktree_path: Optional[str] = None):
        self.enforcer = enforcer or get_security_enforcer()
        self.worktree_path = worktree_path
        self._temp_dirs: List[str] = []
    
    def run(self,
            command: List[str],
            cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None,
            timeout: Optional[int] = None,
            capture_output: bool = True,
            input_data: Optional[str] = None) -> SubprocessResult:
        """Execute a command securely with resource limits.
        
        Args:
            command: Command as list of arguments
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds (overrides policy default)
            capture_output: Whether to capture stdout/stderr
            input_data: Input to pass to stdin
            
        Returns:
            SubprocessResult with execution details
        """
        start_time = time.time()
        
        # Validate command
        is_valid, error_msg = self.enforcer.validate_command(command)
        if not is_valid:
            logger.error(f"Command validation failed: {error_msg}")
            return SubprocessResult(
                returncode=-1,
                stdout="",
                stderr=error_msg,
                duration_ms=0,
                error_message=error_msg
            )
        
        # Validate working directory
        if cwd:
            is_valid, error_msg = self.enforcer.validate_path(cwd, self.worktree_path)
            if not is_valid:
                return SubprocessResult(
                    returncode=-1,
                    stdout="",
                    stderr=error_msg,
                    duration_ms=0,
                    error_message=error_msg
                )
        elif self.worktree_path:
            cwd = self.worktree_path
        
        # Determine timeout
        if timeout is None:
            timeout = self.enforcer.get_timeout_for_command(command)
        
        # Prepare environment
        safe_env = self._prepare_environment(env)
        
        # Create temp directory for output capture if needed
        temp_dir = None
        stdout_file = None
        stderr_file = None
        
        try:
            if capture_output:
                temp_dir = tempfile.mkdtemp(prefix="product_exec_")
                self._temp_dirs.append(temp_dir)
                stdout_path = os.path.join(temp_dir, "stdout.txt")
                stderr_path = os.path.join(temp_dir, "stderr.txt")
                stdout_file = open(stdout_path, "w")
                stderr_file = open(stderr_path, "w")
            
            # Set up resource limits
            preexec_fn = ResourceLimiter(
                max_memory_mb=self.enforcer.policy.max_memory_mb,
                max_cpu_time=timeout
            )
            
            logger.info(f"Executing: {' '.join(command)} (timeout={timeout}s, cwd={cwd})")
            
            # Execute with timeout
            try:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=safe_env,
                    stdout=stdout_file if capture_output else None,
                    stderr=stderr_file if capture_output else None,
                    stdin=subprocess.PIPE if input_data else None,
                    preexec_fn=preexec_fn,
                    # Don't use shell - ever
                    shell=False,
                )
                
                # Handle input data
                if input_data:
                    # Sanitize and encode input
                    input_bytes = input_data.encode('utf-8', errors='ignore')
                    # Limit input size
                    max_input = 10 * 1024 * 1024  # 10MB max input
                    if len(input_bytes) > max_input:
                        input_bytes = input_bytes[:max_input]
                    try:
                        process.stdin.write(input_bytes)
                        process.stdin.close()
                    except BrokenPipeError:
                        pass  # Process may have already exited
                
                # Wait with timeout
                try:
                    returncode = process.wait(timeout=timeout)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    # Kill the process
                    self._kill_process(process)
                    returncode = -9  # SIGKILL
                    timed_out = True
                    logger.warning(f"Command timed out after {timeout}s: {' '.join(command)}")
                
                # Collect output
                stdout = ""
                stderr = ""
                output_truncated = False
                
                if capture_output:
                    stdout_file.close()
                    stderr_file.close()
                    
                    # Read output with size limits
                    max_output = self.enforcer.policy.max_output_size_mb * 1024 * 1024
                    
                    try:
                        with open(stdout_path, "r", errors="ignore") as f:
                            stdout = f.read(max_output)
                            # Check if there's more
                            remaining = f.read(1)
                            if remaining:
                                output_truncated = True
                                stdout += "\n[OUTPUT TRUNCATED]"
                    except Exception as e:
                        stdout = f"[Error reading stdout: {e}]"
                    
                    try:
                        with open(stderr_path, "r", errors="ignore") as f:
                            stderr = f.read(max_output)
                    except Exception as e:
                        stderr = f"[Error reading stderr: {e}]"
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return SubprocessResult(
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=duration_ms,
                    timed_out=timed_out,
                    output_truncated=output_truncated
                )
                
            except OSError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return SubprocessResult(
                    returncode=-1,
                    stdout="",
                    stderr=f"Execution error: {e}",
                    duration_ms=duration_ms,
                    error_message=str(e)
                )
                
        finally:
            if stdout_file:
                stdout_file.close()
            if stderr_file:
                stderr_file.close()
    
    def run_shell(self, command: str, **kwargs) -> SubprocessResult:
        """Execute a shell command - generally blocked for security.
        
        This method exists for compatibility but will reject commands
        unless explicitly enabled in policy.
        """
        is_valid, error_msg = self.enforcer.validate_shell_command(command)
        if not is_valid:
            return SubprocessResult(
                returncode=-1,
                stdout="",
                stderr=error_msg,
                duration_ms=0,
                error_message=error_msg
            )
        
        # If validation passed (shell is enabled), execute with shell=True
        # This should rarely be used
        logger.warning(f"Executing shell command: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=kwargs.get('timeout', 60)
            )
            return SubprocessResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=0
            )
        except subprocess.TimeoutExpired:
            return SubprocessResult(
                returncode=-9,
                stdout="",
                stderr="Command timed out",
                duration_ms=0,
                timed_out=True
            )
    
    def _prepare_environment(self, env: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Prepare a safe environment for subprocess execution."""
        # Start with minimal environment
        safe_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": os.environ.get("HOME", "/tmp"),
            "TMPDIR": tempfile.gettempdir(),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        
        # Add allowed variables from current environment
        allowed_vars = [
            "PYTHONPATH",
            "NODE_PATH",
            "GOPATH",
            "RUSTUP_HOME",
            "CARGO_HOME",
            "JAVA_HOME",
            "MAVEN_OPTS",
            "GRADLE_OPTS",
        ]
        for var in allowed_vars:
            if var in os.environ:
                safe_env[var] = os.environ[var]
        
        # Merge with provided env (provided takes precedence)
        if env:
            # Sanitize env values
            for key, value in env.items():
                # Only allow safe keys
                if self._is_safe_env_key(key):
                    safe_env[key] = self.enforcer.sanitize_input(value)
        
        return safe_env
    
    def _is_safe_env_key(self, key: str) -> bool:
        """Check if an environment variable key is safe."""
        # Block dangerous patterns
        dangerous_patterns = [
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "PATH",
            "SHELL",
            "IFS",
            "PS4",
            "BASH_ENV",
            "ENV",
            "PROMPT_COMMAND",
        ]
        
        key_upper = key.upper()
        for pattern in dangerous_patterns:
            if pattern in key_upper:
                return False
        
        # Only allow alphanumeric and underscore
        if not all(c.isalnum() or c == "_" for c in key):
            return False
        
        return True
    
    def _kill_process(self, process: subprocess.Popen):
        """Kill a process and its children."""
        try:
            # Try graceful termination first
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill
                process.kill()
                process.wait()
        except Exception as e:
            logger.error(f"Error killing process: {e}")
    
    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self._temp_dirs:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")
        self._temp_dirs.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Convenience function for one-off executions
def run_secure(command: List[str],
               cwd: Optional[str] = None,
               timeout: Optional[int] = None,
               worktree_path: Optional[str] = None,
               **kwargs) -> SubprocessResult:
    """Execute a command securely with all protections enabled.
    
    This is a convenience function for simple use cases.
    For repeated use, create a SecureSubprocess instance.
    
    Args:
        command: Command as list of arguments
        cwd: Working directory
        timeout: Timeout in seconds
        worktree_path: Constrain execution to this path
        **kwargs: Additional arguments passed to SecureSubprocess.run()
        
    Returns:
        SubprocessResult
    """
    with SecureSubprocess(worktree_path=worktree_path) as executor:
        return executor.run(command, cwd=cwd, timeout=timeout, **kwargs)
