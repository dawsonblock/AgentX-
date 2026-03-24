"""Initial schema for product runtime.

Revision ID: 001
Revises: 
Create Date: 2026-03-24 14:34:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create runs table
    op.create_table(
        'runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', sa.String(255), nullable=False, index=True),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('goal', sa.Text, nullable=False),
        sa.Column('state', sa.String(50), nullable=False, default='created', index=True),
        sa.Column('worker_profile', sa.String(100), default='gsd-default'),
        sa.Column('constraints_json', sa.JSON, default=dict),
        sa.Column('created_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create run_events table
    op.create_table(
        'run_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('seq', sa.Integer, nullable=False),
        sa.Column('type', sa.String(100), nullable=False, index=True),
        sa.Column('actor_kind', sa.String(50), default='runtime'),
        sa.Column('actor_id', sa.String(255)),
        sa.Column('payload', sa.JSON, default=dict),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('run_id', 'seq', name='uq_run_events_run_id_seq')
    )
    
    # Create worktrees table
    op.create_table(
        'worktrees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('repo_id', sa.String(255), nullable=False),
        sa.Column('path', sa.String(512), nullable=False),
        sa.Column('branch_name', sa.String(255)),
        sa.Column('base_ref', sa.String(255)),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('released_at', sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table('worktrees')
    op.drop_table('run_events')
    op.drop_table('runs')
