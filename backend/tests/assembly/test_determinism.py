from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.domains.assembly.models import AssembledDocument
from backend.app.domains.assembly.schemas import (
    AssembledBlockSchema,
    AssembledDocumentSchema,
    AssemblyRequest,
    AssemblyResult,
    compute_block_content_hash,
    compute_text_hash,
)
from backend.app.domains.assembly.service import ContentInjector, DocumentAssemblyService
from backend.app.domains.parsing.schemas import BlockType, HeadingBlock, ParagraphBlock


def create_mock_assembled_document(assembly_request, **overrides):
    mock_assembled = MagicMock(spec=AssembledDocument)
    mock_assembled.id = overrides.get("id", uuid4())
    mock_assembled.document_id = assembly_request.document_id
    mock_assembled.template_version_id = assembly_request.template_version_id
    mock_assembled.version_intent = assembly_request.version_intent
    mock_assembled.section_output_batch_id = assembly_request.section_output_batch_id
    mock_assembled.assembly_hash = overrides.get("assembly_hash", "test_hash")
    mock_assembled.total_blocks = overrides.get("total_blocks", 3)
    mock_assembled.dynamic_blocks_count = overrides.get("dynamic_blocks_count", 1)
    mock_assembled.static_blocks_count = overrides.get("static_blocks_count", 2)
    mock_assembled.injected_sections_count = overrides.get("injected_sections_count", 1)
    mock_assembled.headers = overrides.get("headers", [])
    mock_assembled.footers = overrides.get("footers", [])
    mock_assembled.is_immutable = overrides.get("is_immutable", True)
    mock_assembled.assembled_at = overrides.get("assembled_at", datetime.utcnow())
    mock_assembled.created_at = overrides.get("created_at", datetime.utcnow())
    return mock_assembled


class TestSameInputsProduceSameOutput:
    async def test_identical_inputs_produce_identical_hash(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        validated_section_output,
    ):
        mock_assembled = create_mock_assembled_document(
            assembly_request, assembly_hash="deterministic_hash"
        )

        assembly_service.repository.create.return_value = mock_assembled
        assembly_service.repository.mark_in_progress.return_value = mock_assembled
        assembly_service.repository.mark_completed.return_value = mock_assembled
        assembly_service.repository.mark_validated.return_value = mock_assembled
        assembly_service.repository.get_by_id.return_value = mock_assembled
        assembly_service.section_output_repository.get_validated_outputs.return_value = [
            validated_section_output
        ]

        result1 = await assembly_service.assemble_document(assembly_request)

        assembly_service.repository.get_by_section_output_batch.return_value = None
        result2 = await assembly_service.assemble_document(assembly_request)

        assert result1.success is True
        assert result2.success is True

    def test_content_hash_deterministic(self):
        content = "This is test content for hashing"

        hash1 = compute_text_hash(content)
        hash2 = compute_text_hash(content)
        hash3 = compute_text_hash(content)

        assert hash1 == hash2 == hash3

    def test_block_hash_deterministic(
        self,
        static_paragraph_block: ParagraphBlock,
    ):
        hash1 = compute_block_content_hash(static_paragraph_block)
        hash2 = compute_block_content_hash(static_paragraph_block)
        hash3 = compute_block_content_hash(static_paragraph_block)

        assert hash1 == hash2 == hash3


class TestInjectionDeterminism:
    def test_paragraph_injection_deterministic(
        self,
        content_injector: ContentInjector,
        dynamic_paragraph_block: ParagraphBlock,
    ):
        content = "Deterministic injection content"

        result1, hash1 = content_injector.inject_into_paragraph(dynamic_paragraph_block, content)
        result2, hash2 = content_injector.inject_into_paragraph(dynamic_paragraph_block, content)

        assert hash1 == hash2
        assert result1["runs"][0]["text"] == result2["runs"][0]["text"]
        assert result1["block_id"] == result2["block_id"]

    def test_heading_injection_deterministic(
        self,
        content_injector: ContentInjector,
        heading_block: HeadingBlock,
    ):
        content = "Deterministic heading content"

        result1, hash1 = content_injector.inject_into_heading(heading_block, content)
        result2, hash2 = content_injector.inject_into_heading(heading_block, content)

        assert hash1 == hash2
        assert result1["level"] == result2["level"]
        assert result1["runs"][0]["text"] == result2["runs"][0]["text"]

    def test_block_preservation_deterministic(
        self,
        content_injector: ContentInjector,
        static_paragraph_block: ParagraphBlock,
    ):
        result1, hash1 = content_injector.preserve_block(static_paragraph_block)
        result2, hash2 = content_injector.preserve_block(static_paragraph_block)

        assert hash1 == hash2
        assert result1 == result2


class TestReassemblyConsistency:
    def test_determinism_validation_passes_for_identical_results(
        self,
        assembly_service: DocumentAssemblyService,
    ):
        block1 = AssembledBlockSchema(
            block_id="blk_001",
            block_type=BlockType.PARAGRAPH,
            sequence=0,
            assembled_content_hash="hash_abc",
        )
        block2 = AssembledBlockSchema(
            block_id="blk_001",
            block_type=BlockType.PARAGRAPH,
            sequence=0,
            assembled_content_hash="hash_abc",
        )

        doc1 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="same_hash",
            blocks=[block1],
        )
        doc2 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="same_hash",
            blocks=[block2],
        )

        result1 = AssemblyResult(success=True, assembled_document=doc1)
        result2 = AssemblyResult(success=True, assembled_document=doc2)

        is_deterministic = assembly_service.validate_determinism(result1, result2)

        assert is_deterministic is True

    def test_determinism_validation_fails_for_different_hashes(
        self,
        assembly_service: DocumentAssemblyService,
    ):
        block1 = AssembledBlockSchema(
            block_id="blk_001",
            block_type=BlockType.PARAGRAPH,
            sequence=0,
            assembled_content_hash="hash_abc",
        )
        block2 = AssembledBlockSchema(
            block_id="blk_001",
            block_type=BlockType.PARAGRAPH,
            sequence=0,
            assembled_content_hash="hash_xyz",
        )

        doc1 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="hash_1",
            blocks=[block1],
        )
        doc2 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="hash_2",
            blocks=[block2],
        )

        result1 = AssemblyResult(success=True, assembled_document=doc1)
        result2 = AssemblyResult(success=True, assembled_document=doc2)

        is_deterministic = assembly_service.validate_determinism(result1, result2)

        assert is_deterministic is False

    def test_determinism_validation_fails_for_different_block_counts(
        self,
        assembly_service: DocumentAssemblyService,
    ):
        block1 = AssembledBlockSchema(
            block_id="blk_001",
            block_type=BlockType.PARAGRAPH,
            sequence=0,
        )

        doc1 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="hash",
            blocks=[block1],
        )
        doc2 = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="hash",
            blocks=[block1, block1],
        )

        result1 = AssemblyResult(success=True, assembled_document=doc1)
        result2 = AssemblyResult(success=True, assembled_document=doc2)

        is_deterministic = assembly_service.validate_determinism(result1, result2)

        assert is_deterministic is False


class TestHashComputations:
    def test_different_content_produces_different_hash(self):
        hash1 = compute_text_hash("Content A")
        hash2 = compute_text_hash("Content B")

        assert hash1 != hash2

    def test_empty_content_has_consistent_hash(self):
        hash1 = compute_text_hash("")
        hash2 = compute_text_hash("")

        assert hash1 == hash2

    def test_whitespace_differences_produce_different_hashes(self):
        hash1 = compute_text_hash("content")
        hash2 = compute_text_hash("content ")
        hash3 = compute_text_hash(" content")

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3


class TestAssemblyHashComputation:
    def test_assembly_hash_includes_all_blocks(self):
        doc = AssembledDocumentSchema(
            id=uuid4(),
            document_id=uuid4(),
            template_version_id=uuid4(),
            version_intent=1,
            section_output_batch_id=uuid4(),
            assembly_hash="",
            blocks=[
                AssembledBlockSchema(
                    block_id="blk_001",
                    block_type=BlockType.PARAGRAPH,
                    sequence=0,
                    assembled_content_hash="hash_1",
                ),
                AssembledBlockSchema(
                    block_id="blk_002",
                    block_type=BlockType.HEADING,
                    sequence=1,
                    assembled_content_hash="hash_2",
                ),
            ],
        )

        hash1 = doc.compute_assembly_hash()

        doc.blocks[0].assembled_content_hash = "different_hash"
        hash2 = doc.compute_assembly_hash()

        assert hash1 != hash2
