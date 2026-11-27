"""analysis trace and evidence notes

Revision ID: 4765aba58c8f
Revises: e648f2ffee94
Create Date: 2026-11-27 17:32:45.041610

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '4765aba58c8f'
down_revision: str | None = 'e648f2ffee94'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('pii_masked', sa.JSON(), nullable=True))
    op.add_column('analyses', sa.Column('trace', sa.JSON(), nullable=True))
    op.add_column('analyses', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('match_evidence', sa.Column('position', sa.Integer(), server_default='0', nullable=False))
    op.add_column('match_evidence', sa.Column('job_quote_verified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('match_evidence', sa.Column('notes', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('match_evidence', 'notes')
    op.drop_column('match_evidence', 'job_quote_verified')
    op.drop_column('match_evidence', 'position')
    op.drop_column('analyses', 'finished_at')
    op.drop_column('analyses', 'trace')
    op.drop_column('analyses', 'pii_masked')
