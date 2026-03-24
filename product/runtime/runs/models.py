"""Run database models."""

from sqlalchemy import Column, String, JSON, DateTime, Text, ForeignKey, Integer
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


class Patch(Base):
    """A patch proposal produced by a worker."""
    
    __tablename__ = "patches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False, index=True)
    worktree_id = Column(String(255))
    base_commit = Column(String(255))
    diff_text = Column(Text, nullable=False)
    summary = Column(Text)
    status = Column(String(50), default="proposed")  # proposed | approved | rejected | applied
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "worktree_id": self.worktree_id,
            "base_commit": self.base_commit,
            "diff_text": self.diff_text,
            "summary": self.summary,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Approval(Base):
    """An approval decision for a patch."""
    
    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    patch_id = Column(UUID(as_uuid=True), ForeignKey("patches.id"), nullable=False, index=True)
    decision = Column(String(50), nullable=False)  # approve | reject
    reason = Column(Text)
    actor_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "patch_id": str(self.patch_id),
            "decision": self.decision,
            "reason": self.reason,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Artifact(Base):
    """An artifact produced during a run (logs, test output, etc.)."""
    
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(String(100), nullable=False)  # log | test | patch | report | context
    filename = Column(String(255))
    path = Column(String(512))
    size_bytes = Column(Integer)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "type": self.type,
            "filename": self.filename,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProvenanceRecord(Base):
    """A provenance record tracking the origin of code changes."""
    
    __tablename__ = "provenance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    patch_id = Column(UUID(as_uuid=True), ForeignKey("patches.id"))
    step_name = Column(String(255))
    input_data = Column(JSON)
    output_data = Column(JSON)
    tool_chain = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "patch_id": str(self.patch_id) if self.patch_id else None,
            "step_name": self.step_name,
            "input": self.input_data or {},
            "output": self.output_data or {},
            "tool_chain": self.tool_chain or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
