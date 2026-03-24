"""Add CI checks table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-24 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ci_checks table
    op.create_table(
        'ci_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patches.id'), nullable=False, index=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('gate_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('exit_code', sa.Integer),
        sa.Column('stdout', sa.Text),
        sa.Column('stderr', sa.Text),
        sa.Column('duration_ms', sa.Integer),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('ci_checks')
