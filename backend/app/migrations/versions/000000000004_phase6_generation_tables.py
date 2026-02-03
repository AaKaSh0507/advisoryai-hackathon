from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "000000000004"
down_revision: Union[str, None] = "000000000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    generation_input_status_enum = sa.Enum(
        "PENDING", "VALIDATED", "FAILED", name="generation_input_status_enum"
    )
    generation_input_status_enum.create(op.get_bind(), checkfirst=True)

    section_generation_status_enum = sa.Enum(
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "RETRYING",
        "VALIDATED",
        name="section_generation_status_enum",
    )
    section_generation_status_enum.create(op.get_bind(), checkfirst=True)

    assembly_status_enum = sa.Enum(
        "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "VALIDATED", name="assembly_status_enum"
    )
    assembly_status_enum.create(op.get_bind(), checkfirst=True)

    render_status_enum = sa.Enum(
        "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "VALIDATED", name="render_status_enum"
    )
    render_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "generation_input_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_intent", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "VALIDATED",
                "FAILED",
                name="generation_input_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("total_inputs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["template_versions.id"]),
    )
    op.create_index(
        "ix_generation_input_batches_document", "generation_input_batches", ["document_id"]
    )
    op.create_index(
        "ix_generation_input_batches_template_version",
        "generation_input_batches",
        ["template_version_id"],
    )
    op.create_index(
        "ix_generation_input_batches_document_version",
        "generation_input_batches",
        ["document_id", "version_intent"],
    )

    op.create_table(
        "generation_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("structural_path", sa.String(), nullable=False),
        sa.Column("hierarchy_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("client_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("surrounding_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["batch_id"], ["generation_input_batches.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
    )
    op.create_index("ix_generation_inputs_batch", "generation_inputs", ["batch_id"])
    op.create_index("ix_generation_inputs_section", "generation_inputs", ["section_id"])
    op.create_index(
        "ix_generation_inputs_batch_sequence", "generation_inputs", ["batch_id", "sequence_order"]
    )

    op.create_table(
        "section_output_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_intent", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "RETRYING",
                "VALIDATED",
                name="section_generation_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("total_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["input_batch_id"], ["generation_input_batches.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
    )
    op.create_index(
        "ix_section_output_batches_input_batch", "section_output_batches", ["input_batch_id"]
    )
    op.create_index("ix_section_output_batches_document", "section_output_batches", ["document_id"])
    op.create_index(
        "ix_section_output_batches_document_version",
        "section_output_batches",
        ["document_id", "version_intent"],
    )

    op.create_table(
        "section_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_input_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "RETRYING",
                "VALIDATED",
                name="section_generation_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("generated_content", sa.Text(), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("failure_category", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("retry_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["batch_id"], ["section_output_batches.id"]),
        sa.ForeignKeyConstraint(["generation_input_id"], ["generation_inputs.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
    )
    op.create_index("ix_section_outputs_batch", "section_outputs", ["batch_id"])
    op.create_index("ix_section_outputs_section", "section_outputs", ["section_id"])
    op.create_index(
        "ix_section_outputs_generation_input", "section_outputs", ["generation_input_id"]
    )
    op.create_index(
        "ix_section_outputs_batch_sequence", "section_outputs", ["batch_id", "sequence_order"]
    )
    op.create_index("ix_section_outputs_failure_category", "section_outputs", ["failure_category"])
    op.create_index("ix_section_outputs_status", "section_outputs", ["status"])

    op.create_table(
        "assembled_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_intent", sa.Integer(), nullable=False),
        sa.Column("section_output_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "VALIDATED",
                name="assembly_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("assembly_hash", sa.String(64), nullable=False),
        sa.Column("total_blocks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dynamic_blocks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("static_blocks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("injected_sections_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assembled_structure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("injection_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("footers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("assembly_duration_ms", sa.Float(), nullable=True),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("assembled_at", sa.DateTime(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["template_versions.id"]),
        sa.ForeignKeyConstraint(["section_output_batch_id"], ["section_output_batches.id"]),
    )
    op.create_index("ix_assembled_documents_document", "assembled_documents", ["document_id"])
    op.create_index(
        "ix_assembled_documents_template_version", "assembled_documents", ["template_version_id"]
    )
    op.create_index(
        "ix_assembled_documents_section_output_batch",
        "assembled_documents",
        ["section_output_batch_id"],
    )
    op.create_index(
        "ix_assembled_documents_document_version",
        "assembled_documents",
        ["document_id", "version_intent"],
    )
    op.create_index("ix_assembled_documents_status", "assembled_documents", ["status"])
    op.create_index(
        "ix_assembled_documents_assembly_hash", "assembled_documents", ["assembly_hash"]
    )

    op.create_table(
        "rendered_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assembled_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "VALIDATED",
                name="render_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("output_path", sa.String(512), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_blocks_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paragraphs_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tables_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lists_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headings_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headers_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("footers_rendered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rendering_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("rendering_duration_ms", sa.Float(), nullable=True),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rendered_at", sa.DateTime(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assembled_document_id"], ["assembled_documents.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
    )
    op.create_index(
        "ix_rendered_documents_assembled", "rendered_documents", ["assembled_document_id"]
    )
    op.create_index("ix_rendered_documents_document", "rendered_documents", ["document_id"])
    op.create_index(
        "ix_rendered_documents_document_version", "rendered_documents", ["document_id", "version"]
    )
    op.create_index("ix_rendered_documents_status", "rendered_documents", ["status"])
    op.create_index("ix_rendered_documents_content_hash", "rendered_documents", ["content_hash"])


def downgrade() -> None:
    op.drop_table("rendered_documents")
    op.drop_table("assembled_documents")
    op.drop_table("section_outputs")
    op.drop_table("section_output_batches")
    op.drop_table("generation_inputs")
    op.drop_table("generation_input_batches")

    sa.Enum(name="render_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assembly_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="section_generation_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="generation_input_status_enum").drop(op.get_bind(), checkfirst=True)
