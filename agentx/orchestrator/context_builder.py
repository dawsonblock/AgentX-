"""Context builder - builds context for LLM from repository."""

import os
from typing import List, Dict, Any

from core.config import Settings
from core.logging import get_logger

logger = get_logger(__name__)


def _rank_files(repo_path: str, task: str) -> List[str]:
    """Rank files by relevance to task.
    
    Simple keyword matching on filenames.
    
    Args:
        repo_path: Repository path
        task: Task description
        
    Returns:
        List of file paths ranked by relevance
    """
    keywords = [w.lower() for w in task.split() if len(w) > 2]
    hits = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in (
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            '.pytest_cache', '.mypy_cache', 'build', 'dist'
        )]
        
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip binary and large files
            try:
                if os.path.getsize(filepath) > 1000000:  # 1MB
                    continue
            except OSError:
                continue
            
            # Score by keyword matches in filename
            filename_lower = filename.lower()
            score = sum(1 for k in keywords if k in filename_lower)
            
            if score > 0:
                hits.append((score, filepath))
    
    # Sort by score descending
    hits.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in hits]


def _is_text_file(path: str) -> bool:
    """Check if a file is a text file we can read.
    
    Args:
        path: File path
        
    Returns:
        True if text file
    """
    text_extensions = (
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
        '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
        '.kt', '.scala', '.r', '.m', '.mm', '.sql', '.sh', '.bash',
        '.zsh', '.fish', '.ps1', '.yaml', '.yml', '.json', '.xml',
        '.toml', '.ini', '.cfg', '.conf', '.md', '.rst', '.txt',
        '.html', '.htm', '.css', '.scss', '.sass', '.less', '.vue',
        '.svelte', '.graphql', '.proto'
    )
    
    return any(path.lower().endswith(ext) for ext in text_extensions)


def build_context(repo_path: str, task: str) -> List[Dict[str, Any]]:
    """Build context for a task from a repository.
    
    Args:
        repo_path: Repository path
        task: Task description
        
    Returns:
        List of context items with path and content
    """
    ranked_files = _rank_files(repo_path, task)[:Settings.MAX_CONTEXT_FILES]
    
    context = []
    for filepath in ranked_files:
        if not _is_text_file(filepath):
            continue
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(Settings.MAX_FILE_CHARS)
            
            rel_path = os.path.relpath(filepath, repo_path)
            context.append({
                "path": rel_path,
                "content": content,
                "size": len(content)
            })
        except Exception as e:
            logger.warning(f"Could not read {filepath}: {e}")
            continue
    
    logger.info(f"Built context with {len(context)} files for task")
    return context
