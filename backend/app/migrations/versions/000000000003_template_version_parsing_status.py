from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "000000000003"
down_revision: Union[str, None] = "000000000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    parsing_status_enum = sa.Enum(
        "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", name="parsing_status_enum"
    )
    parsing_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "template_versions",
        sa.Column(
            "parsing_status",
            postgresql.ENUM(
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                name="parsing_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
    )

    op.add_column("template_versions", sa.Column("parsing_error", sa.String(), nullable=True))
    op.add_column("template_versions", sa.Column("parsed_at", sa.DateTime(), nullable=True))
    op.add_column("template_versions", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index("ix_template_versions_parsing_status", "template_versions", ["parsing_status"])


def downgrade() -> None:
    op.drop_index("ix_template_versions_parsing_status", table_name="template_versions")
    op.drop_column("template_versions", "content_hash")
    op.drop_column("template_versions", "parsed_at")
    op.drop_column("template_versions", "parsing_error")
    op.drop_column("template_versions", "parsing_status")
    sa.Enum(name="parsing_status_enum").drop(op.get_bind(), checkfirst=True)
