"""Context Service - Python wrapper for context building.

Provides context building capabilities to the runtime.
Can call the TypeScript packer via subprocess or use native Python implementation.
"""

import os
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


class ContextService:
    """Service for building bounded context from worktrees."""

    def __init__(self):
        """Initialize context service."""
        self.max_file_size = 100 * 1024  # 100KB
        self.max_files = 50

    def discover_files(self, worktree_path: str) -> List[str]:
        """Discover relevant source files in worktree.
        
        Args:
            worktree_path: Path to worktree
            
        Returns:
            List of relative file paths
        """
        files = []
        
        # Common source extensions
        source_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.java', '.go', '.rs', '.cpp', '.c', '.h',
            '.rb', '.php', '.swift', '.kt'
        }
        
        # Directories to skip
        skip_dirs = {
            'node_modules', '.git', '__pycache__', '.venv',
            'venv', 'dist', 'build', '.pytest_cache',
            '.mypy_cache', '.tox', '.eggs', '*.egg-info'
        }
        
        try:
            for root, dirs, filenames in os.walk(worktree_path):
                # Skip unwanted directories
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                
                for filename in filenames:
                    ext = Path(filename).suffix.lower()
                    if ext in source_extensions:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, worktree_path)
                        files.append(rel_path)
                        
                        if len(files) >= self.max_files:
                            break
                
                if len(files) >= self.max_files:
                    break
                    
        except Exception as e:
            print(f"Error discovering files: {e}")
        
        return files

    def read_file(self, worktree_path: str, file_path: str) -> Optional[str]:
        """Read a file from worktree.
        
        Args:
            worktree_path: Path to worktree
            file_path: Relative file path
            
        Returns:
            File content or None
        """
        full_path = os.path.join(worktree_path, file_path)
        
        try:
            # Check file size
            size = os.path.getsize(full_path)
            if size > self.max_file_size:
                return f"// File: {file_path}\n// (File too large: {size} bytes)"
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        except Exception:
            return None

    def build_context(
        self,
        worktree_path: str,
        task_description: str,
        candidate_files: Optional[List[str]] = None,
        failing_test_logs: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build context pack for a task.
        
        Args:
            worktree_path: Path to worktree
            task_description: Task description
            candidate_files: Optional list of candidate files
            failing_test_logs: Optional failing test logs
            
        Returns:
            Context pack dictionary
        """
        # Discover files if not provided
        if not candidate_files:
            candidate_files = self.discover_files(worktree_path)
        
        # Load file contents
        files_with_content = []
        for file_path in candidate_files[:self.max_files]:
            content = self.read_file(worktree_path, file_path)
            if content:
                # Truncate if too long
                max_chars = 16000  # ~4000 tokens
                if len(content) > max_chars:
                    content = content[:max_chars] + '\n\n// ... (truncated)'
                
                files_with_content.append({
                    "path": file_path,
                    "content": content,
                    "size": len(content)
                })
        
        # Build the context
        context = {
            "task": task_description,
            "worktree_path": worktree_path,
            "files": files_with_content,
            "file_count": len(files_with_content),
            "discovered_files": len(candidate_files)
        }
        
        if failing_test_logs:
            context["failing_tests"] = failing_test_logs[:5000]  # Limit size
        
        return context

    def build_context_via_node(
        self,
        worktree_path: str,
        task_description: str
    ) -> Optional[Dict[str, Any]]:
        """Build context using the TypeScript packer via Node.js.
        
        Args:
            worktree_path: Path to worktree
            task_description: Task description
            
        Returns:
            Context pack or None if Node.js not available
        """
        try:
            # Check if node is available
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            # Build and run TypeScript
            script_path = os.path.join(
                os.path.dirname(__file__),
                'context_packer',
                'run_packer.js'
            )
            
            if not os.path.exists(script_path):
                # Create a simple runner script
                self._create_runner_script(script_path)
            
            # Run the packer
            result = subprocess.run(
                ['node', script_path, worktree_path, task_description],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                print(f"Context packer error: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Failed to run Node.js context packer: {e}")
            return None

    def _create_runner_script(self, script_path: str) -> None:
        """Create a Node.js runner script for the TypeScript packer.
        
        Args:
            script_path: Path to create script
        """
        script_content = '''
const { buildContextWithDiscovery } = require('./pack');

async function main() {
  const worktreePath = process.argv[2];
  const taskDescription = process.argv[3];
  
  try {
    const context = await buildContextWithDiscovery(worktreePath, taskDescription);
    console.log(JSON.stringify(context));
  } catch (error) {
    console.error(error);
    process.exit(1);
  }
}

main();
'''
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        with open(script_path, 'w') as f:
            f.write(script_content)


# Global service instance
_service: Optional[ContextService] = None


def get_service() -> ContextService:
    """Get the global service instance.
    
    Returns:
        ContextService instance
    """
    global _service
    if _service is None:
        _service = ContextService()
    return _service
