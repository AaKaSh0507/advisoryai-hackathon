"""initial_schema

Revision ID: 000000000001
Revises: 
Create Date: 2024-02-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '000000000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUMS
    sa.Enum('STATIC', 'DYNAMIC', name='section_type_enum').create(op.get_bind())
    sa.Enum('PARSE', 'CLASSIFY', 'GENERATE', name='job_type_enum').create(op.get_bind())
    sa.Enum('PENDING', 'RUNNING', 'FAILED', 'COMPLETED', name='job_status_enum').create(op.get_bind())

    # 1. templates
    op.create_table('templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. template_versions
    op.create_table('template_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('source_doc_path', sa.String(), nullable=False),
        sa.Column('parsed_representation_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
        sa.UniqueConstraint('template_id', 'version_number', name='uq_template_version')
    )

    # 3. sections
    op.create_table('sections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_type', postgresql.ENUM('STATIC', 'DYNAMIC', name='section_type_enum', create_type=False), nullable=False),
        sa.Column('structural_path', sa.String(), nullable=False),
        sa.Column('prompt_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_version_id'], ['template_versions.id'], )
    )

    # 4. documents
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('current_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_version_id'], ['template_versions.id'], )
    )

    # 5. document_versions
    op.create_table('document_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('output_doc_path', sa.String(), nullable=False),
        sa.Column('generation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_document_version')
    )

    # 6. jobs
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', postgresql.ENUM('PARSE', 'CLASSIFY', 'GENERATE', name='job_type_enum', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'FAILED', 'COMPLETED', name='job_status_enum', create_type=False), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. audit_logs
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('jobs')
    op.drop_table('document_versions')
    op.drop_table('documents')
    op.drop_table('sections')
    op.drop_table('template_versions')
    op.drop_table('templates')

    sa.Enum(name='job_status_enum').drop(op.get_bind())
    sa.Enum(name='job_type_enum').drop(op.get_bind())
    sa.Enum(name='section_type_enum').drop(op.get_bind())
