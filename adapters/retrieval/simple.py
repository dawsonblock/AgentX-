"""Simple retrieval implementation.

Basic file-based retrieval without external dependencies.
"""

import os
from typing import Dict, Any, List

from .interface import Retrieval


class SimpleRetrieval(Retrieval):
    """Simple file-based retrieval."""
    
    MAX_FILES = 20
    MAX_FILE_SIZE = 5000
    
    def build_context(self, repo_path: str, task: str) -> Dict[str, Any]:
        """Build context by walking repo and reading files."""
        files = []
        keywords = [w.lower() for w in task.split() if len(w) > 2]
        
        scored_files = []
        
        for root, dirs, filenames in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in (
                '.git', '__pycache__', 'node_modules', '.venv', 'venv',
                '.pytest_cache', '.mypy_cache', 'build', 'dist'
            )]
            
            for filename in filenames:
                filepath = os.path.join(root, filename)
                
                # Skip large and binary files
                try:
                    size = os.path.getsize(filepath)
                    if size > 100000:  # 100KB
                        continue
                except OSError:
                    continue
                
                # Score by keyword matches in filename
                filename_lower = filename.lower()
                score = sum(1 for k in keywords if k in filename_lower)
                
                if score > 0 or any(filename.endswith(ext) for ext in ['.py', '.js', '.ts', '.md']):
                    scored_files.append((score, filepath))
        
        # Sort by score and take top files
        scored_files.sort(reverse=True, key=lambda x: x[0])
        
        for _, filepath in scored_files[:self.MAX_FILES]:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(self.MAX_FILE_SIZE)
                
                rel_path = os.path.relpath(filepath, repo_path)
                files.append({
                    "path": rel_path,
                    "content": content,
                    "size": len(content)
                })
            except Exception:
                continue
        
        return {
            "task": task,
            "repo_path": repo_path,
            "files": files,
            "file_count": len(files)
        }
