from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.domains.assembly.models import AssembledDocument
from backend.app.domains.assembly.schemas import (
    AssemblyErrorCode,
    AssemblyRequest,
    AssemblyValidationResult,
)
from backend.app.domains.assembly.service import (
    DocumentAssemblyService,
    StructuralIntegrityValidator,
)
from backend.app.domains.parsing.schemas import ParagraphBlock
from backend.app.domains.section.models import Section


class TestAssemblyFailsWithoutValidatedContent:
    async def test_fails_when_dynamic_section_lacks_validated_content(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        dynamic_section: Section,
    ):
        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = []

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.error_code == AssemblyErrorCode.MISSING_VALIDATED_CONTENT

    async def test_fails_when_output_not_validated(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        dynamic_section: Section,
    ):
        unvalidated_output = MagicMock()
        unvalidated_output.id = uuid4()
        unvalidated_output.section_id = dynamic_section.id
        unvalidated_output.generated_content = "Some content"
        unvalidated_output.is_validated = False

        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            unvalidated_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.validation_result is not None
        assert AssemblyErrorCode.INVALID_SECTION_OUTPUT in result.validation_result.error_codes

    async def test_fails_when_output_has_no_content(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        dynamic_section: Section,
    ):
        empty_output = MagicMock()
        empty_output.id = uuid4()
        empty_output.section_id = dynamic_section.id
        empty_output.generated_content = None
        empty_output.is_validated = True

        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            empty_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.validation_result is not None
        assert AssemblyErrorCode.MISSING_VALIDATED_CONTENT in result.validation_result.error_codes


class TestAssemblyFailsOnStructuralMismatch:
    def test_block_count_mismatch_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
        dynamic_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block, dynamic_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
            }
        ]

        result = structural_validator.validate_block_preservation(original_blocks, assembled_blocks)

        assert result.is_valid is False
        assert AssemblyErrorCode.BLOCK_COUNT_MISMATCH in result.error_codes

    def test_missing_block_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
        dynamic_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block, dynamic_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
            },
            {
                "block_id": "different_block_id",
                "block_type": "paragraph",
            },
        ]

        result = structural_validator.validate_block_preservation(original_blocks, assembled_blocks)

        assert result.is_valid is False
        assert AssemblyErrorCode.ORPHANED_BLOCK in result.error_codes

    def test_extra_block_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
            },
            {
                "block_id": "extra_block_id",
                "block_type": "paragraph",
            },
        ]

        result = structural_validator.validate_block_preservation(original_blocks, assembled_blocks)

        assert result.is_valid is False
        assert AssemblyErrorCode.BLOCK_COUNT_MISMATCH in result.error_codes

    def test_block_order_mismatch_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
        dynamic_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block, dynamic_paragraph_block]
        assembled_blocks = [
            {
                "block_id": dynamic_paragraph_block.block_id,
                "block_type": "paragraph",
            },
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
            },
        ]

        result = structural_validator.validate_block_preservation(original_blocks, assembled_blocks)

        assert result.is_valid is False
        assert AssemblyErrorCode.BLOCK_ORDER_MISMATCH in result.error_codes

    def test_block_type_mismatch_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "heading",
            },
        ]

        result = structural_validator.validate_block_preservation(original_blocks, assembled_blocks)

        assert result.is_valid is False
        assert AssemblyErrorCode.STRUCTURAL_MISMATCH in result.error_codes


class TestStaticBlockModificationDetected:
    def test_static_section_modification_detected(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
    ):
        original_blocks = [static_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
                "assembled_content_hash": "different_hash",
            }
        ]
        static_block_ids = {static_paragraph_block.block_id}

        result = structural_validator.validate_static_sections_unchanged(
            original_blocks, assembled_blocks, static_block_ids
        )

        assert result.is_valid is False
        assert AssemblyErrorCode.STATIC_SECTION_MODIFIED in result.error_codes

    def test_static_section_unchanged_passes(
        self,
        structural_validator: StructuralIntegrityValidator,
        static_paragraph_block: ParagraphBlock,
    ):
        from backend.app.domains.assembly.schemas import compute_block_content_hash

        original_hash = compute_block_content_hash(static_paragraph_block)

        original_blocks = [static_paragraph_block]
        assembled_blocks = [
            {
                "block_id": static_paragraph_block.block_id,
                "block_type": "paragraph",
                "assembled_content_hash": original_hash,
            }
        ]
        static_block_ids = {static_paragraph_block.block_id}

        result = structural_validator.validate_static_sections_unchanged(
            original_blocks, assembled_blocks, static_block_ids
        )

        assert result.is_valid is True


class TestNoSilentCorrections:
    async def test_missing_parsed_template_fails_explicitly(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
    ):
        assembly_service.parsed_document_repository.get_by_template_version_id.return_value = None

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.error_code == AssemblyErrorCode.MISSING_PARSED_TEMPLATE
        assert result.error_message is not None

    async def test_existing_immutable_assembly_fails_without_force(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
    ):
        existing_assembly = MagicMock(spec=AssembledDocument)
        existing_assembly.is_immutable = True

        assembly_service.repository.get_by_section_output_batch.return_value = existing_assembly

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.error_code == AssemblyErrorCode.ASSEMBLY_ALREADY_EXISTS

    async def test_validation_errors_not_suppressed(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        dynamic_section: Section,
    ):
        invalid_output = MagicMock()
        invalid_output.id = uuid4()
        invalid_output.section_id = dynamic_section.id
        invalid_output.generated_content = ""
        invalid_output.is_validated = True

        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            invalid_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is False
        assert result.validation_result is not None
        assert len(result.validation_result.error_codes) > 0


class TestInputValidation:
    def test_validation_result_accumulates_errors(self):
        result = AssemblyValidationResult()

        result.add_error(AssemblyErrorCode.MISSING_VALIDATED_CONTENT, "First error")
        result.add_error(AssemblyErrorCode.STRUCTURAL_MISMATCH, "Second error")

        assert result.is_valid is False
        assert len(result.error_codes) == 2
        assert len(result.error_messages) == 2

    def test_validation_result_starts_valid(self):
        result = AssemblyValidationResult()

        assert result.is_valid is True
        assert len(result.error_codes) == 0
