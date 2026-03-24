"""Central configuration. No scattered env reads."""

import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""
    
    # Database
    DB_URL: str = os.getenv("AGENTX_DB_URL", "sqlite:///./agentx.db")
    
    # Worktree
    WORKTREE_ROOT: str = os.getenv("AGENTX_WORKTREE_ROOT", "./worktrees")
    
    # Context
    MAX_CONTEXT_FILES: int = int(os.getenv("AGENTX_MAX_CONTEXT_FILES", "20"))
    MAX_FILE_CHARS: int = int(os.getenv("AGENTX_MAX_FILE_CHARS", "5000"))
    
    # Worker
    WORKER_MAX_STEPS: int = int(os.getenv("AGENTX_WORKER_MAX_STEPS", "20"))
    WORKER_TIMEOUT_SEC: int = int(os.getenv("AGENTX_WORKER_TIMEOUT_SEC", "120"))
    
    # Queue
    QUEUE_POLL_SEC: int = int(os.getenv("AGENTX_QUEUE_POLL_SEC", "1"))
    
    # Security
    KIMI_API_KEY: Optional[str] = os.getenv("KIMI_API_KEY")
    KIMI_BASE_URL: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "kimi-latest")
    
    # Validation
    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration. Returns list of errors."""
        errors = []
        
        if not cls.KIMI_API_KEY:
            errors.append("KIMI_API_KEY not set (required for LLM worker)")
        
        if cls.WORKER_MAX_STEPS < 1:
            errors.append("WORKER_MAX_STEPS must be >= 1")
        
        if cls.WORKER_TIMEOUT_SEC < 10:
            errors.append("WORKER_TIMEOUT_SEC must be >= 10")
        
        return errors


# Global settings instance
settings = Settings()
