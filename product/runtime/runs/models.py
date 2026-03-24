"""Run database models."""

from sqlalchemy import Column, String, JSON, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from ..db.base import Base


class Run(Base):
    """A coding run represents a single task execution."""
    
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(String(255), nullable=False, index=True)
    task_type = Column(String(100), nullable=False)
    goal = Column(Text, nullable=False)
    state = Column(String(50), nullable=False, default="created", index=True)
    worker_profile = Column(String(100), default="gsd-default")
    constraints_json = Column(JSON, default=dict)
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "repo_id": self.repo_id,
            "task_type": self.task_type,
            "goal": self.goal,
            "state": self.state,
            "worker_profile": self.worker_profile,
            "constraints": self.constraints_json or {},
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Worktree(Base):
    """Tracks allocated worktrees for runs."""
    
    __tablename__ = "worktrees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    repo_id = Column(String(255), nullable=False)
    path = Column(String(512), nullable=False)
    branch_name = Column(String(255))
    base_ref = Column(String(255))
    status = Column(String(50), default="active")  # active, released, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime)

    def to_dict(self):
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "repo_id": self.repo_id,
            "path": self.path,
            "branch_name": self.branch_name,
            "base_ref": self.base_ref,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "released_at": self.released_at.isoformat() if self.released_at else None,
        }
