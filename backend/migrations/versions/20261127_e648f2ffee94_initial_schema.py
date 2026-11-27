"""initial schema

Revision ID: e648f2ffee94
Revises: 
Create Date: 2026-11-27 13:05:50.977640

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e648f2ffee94'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('job_postings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('source_url', sa.String(length=500), nullable=True),
    sa.Column('source_status_checked', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deadline', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resumes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('masked_text', sa.Text(), nullable=False),
    sa.Column('is_sample', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('analyses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'running', 'done', 'failed', name='analysis_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('coverage', sa.JSON(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('prompt_version', sa.String(length=50), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job_postings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analyses_job_id'), 'analyses', ['job_id'], unique=False)
    op.create_index(op.f('ix_analyses_resume_id'), 'analyses', ['resume_id'], unique=False)
    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('stage', sa.Enum('interested', 'planned', 'applied', 'document_passed', 'interview', 'offer', 'rejected', 'withdrawn', name='application_stage', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('applied_at', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job_postings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_applications_job_id'), 'applications', ['job_id'], unique=False)
    op.create_table('match_evidence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('analysis_id', sa.Integer(), nullable=False),
    sa.Column('requirement', sa.Text(), nullable=False),
    sa.Column('requirement_type', sa.Enum('required', 'preferred', 'constraint', name='requirement_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('job_quote', sa.Text(), nullable=True),
    sa.Column('resume_quote', sa.Text(), nullable=True),
    sa.Column('verdict', sa.Enum('met', 'not_met', 'insufficient', name='verdict', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('span_verified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('semantic_verified', sa.Boolean(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('user_edited', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_evidence_analysis_id'), 'match_evidence', ['analysis_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_evidence_analysis_id'), table_name='match_evidence')
    op.drop_table('match_evidence')
    op.drop_index(op.f('ix_applications_job_id'), table_name='applications')
    op.drop_table('applications')
    op.drop_index(op.f('ix_analyses_resume_id'), table_name='analyses')
    op.drop_index(op.f('ix_analyses_job_id'), table_name='analyses')
    op.drop_table('analyses')
    op.drop_table('resumes')
    op.drop_table('job_postings')
