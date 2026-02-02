from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "000000000002"
down_revision: Union[str, None] = "000000000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("jobs", sa.Column("worker_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime(), nullable=True))
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
