"""job_system_enhancements

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-02-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "000000000002"
down_revision: Union[str, None] = "000000000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to jobs table
    op.add_column("jobs", sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("jobs", sa.Column("worker_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime(), nullable=True))

    # Add indexes for efficient job queries
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])
    op.create_index("ix_jobs_payload_entity", "jobs", ["payload"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_jobs_payload_entity", table_name="jobs")
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_column("jobs", "completed_at")
    op.drop_column("jobs", "started_at")
    op.drop_column("jobs", "worker_id")
    op.drop_column("jobs", "result")
