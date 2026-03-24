"""Add patches, approvals, artifacts, and provenance tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-24 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create patches table
    op.create_table(
        'patches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runs.id'), nullable=False, index=True),
        sa.Column('worktree_id', sa.String(255)),
        sa.Column('base_commit', sa.String(255)),
        sa.Column('diff_text', sa.Text, nullable=False),
        sa.Column('summary', sa.Text),
        sa.Column('status', sa.String(50), server_default='proposed'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create approvals table
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('patch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patches.id'), nullable=False, index=True),
        sa.Column('decision', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('actor_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Create index on approvals for patch lookups
    op.create_index('ix_approvals_patch_id', 'approvals', ['patch_id'])
    
    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(255)),
        sa.Column('path', sa.String(512)),
        sa.Column('size_bytes', sa.Integer),
        sa.Column('metadata_json', sa.JSON, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Create provenance_records table
    op.create_table(
        'provenance_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('patch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patches.id')),
        sa.Column('step_name', sa.String(255)),
        sa.Column('input_data', sa.JSON, server_default='{}'),
        sa.Column('output_data', sa.JSON, server_default='{}'),
        sa.Column('tool_chain', sa.JSON, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Create index on provenance for patch lookups
    op.create_index('ix_provenance_records_patch_id', 'provenance_records', ['patch_id'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('provenance_records')
    op.drop_table('artifacts')
    op.drop_table('approvals')
    op.drop_table('patches')
