"""Database models for AgentX."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship

from db.base import Base


def uid() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


class Run(Base):
    """A coding run/task."""
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True, default=uid)
    task = Column(Text, nullable=False)
    repo = Column(String, nullable=False)
    state = Column(String, default="created", nullable=False)
    worktree_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patches = relationship("Patch", back_populates="run", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")
    provenance = relationship("Provenance", back_populates="run", cascade="all, delete-orphan")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Run(id={self.id}, state={self.state})>"


class Patch(Base):
    """A generated code patch/diff."""
    __tablename__ = "patches"
    
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    diff = Column(Text, nullable=False)
    status = Column(String, default="proposed", nullable=False)
    summary = Column(Text, nullable=True)
    base_commit = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    run = relationship("Run", back_populates="patches")
    approvals = relationship("Approval", back_populates="patch", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Patch(id={self.id}, status={self.status})>"


class Approval(Base):
    """An approval decision on a patch."""
    __tablename__ = "approvals"
    
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    patch_id = Column(String, ForeignKey("patches.id"), nullable=False)
    decision = Column(String, nullable=False)  # approve|reject
    reason = Column(Text, nullable=True)
    actor_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    run = relationship("Run", back_populates="approvals")
    patch = relationship("Patch", back_populates="approvals")
    
    def __repr__(self) -> str:
        return f"<Approval(id={self.id}, decision={self.decision})>"


class Artifact(Base):
    """An artifact produced during a run."""
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    path = Column(String, nullable=False)
    type = Column(String, nullable=False)  # log, test, context, etc.
    meta = Column(JSON, default=dict)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    run = relationship("Run", back_populates="artifacts")
    
    def __repr__(self) -> str:
        return f"<Artifact(id={self.id}, type={self.type})>"


class Provenance(Base):
    """Provenance/trace record for a run step."""
    __tablename__ = "provenance"
    
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    step = Column(String, nullable=False)
    input_data = Column("input", JSON, default=dict)
    output_data = Column("output", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    run = relationship("Run", back_populates="provenance")
    
    def __repr__(self) -> str:
        return f"<Provenance(id={self.id}, step={self.step})>"


class RunEvent(Base):
    """Append-only event log for runs."""
    __tablename__ = "run_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    seq = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    actor_kind = Column(String, nullable=True)
    actor_id = Column(String, nullable=True)
    
    # Relationships
    run = relationship("Run", back_populates="events")
    
    def __repr__(self):
        return f"<RunEvent(run_id={self.run_id}, seq={self.seq}, type={self.type})>"
