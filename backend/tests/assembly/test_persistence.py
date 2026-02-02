from uuid import uuid4

import pytest

from backend.app.domains.assembly.models import AssembledDocument, AssemblyStatus
from backend.app.domains.assembly.repository import AssembledDocumentRepository


class TestAssembledDocumentPersistence:
    @pytest.mark.asyncio
    async def test_assembled_document_created_with_correct_fields(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="initial_hash_123",
        )

        assert assembled_doc.id is not None
        assert assembled_doc.document_id == document_id
        assert assembled_doc.template_version_id == template_version_id
        assert assembled_doc.version_intent == 1
        assert assembled_doc.section_output_batch_id == section_output_batch_id
        assert assembled_doc.status == AssemblyStatus.PENDING

    @pytest.mark.asyncio
    async def test_assembled_document_retrieved_by_id(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        created = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        retrieved = await repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.document_id == document_id

    @pytest.mark.asyncio
    async def test_assembled_document_retrieved_by_document_and_version(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        retrieved = await repo.get_by_document_and_version(document_id, 1)

        assert retrieved is not None
        assert retrieved.document_id == document_id
        assert retrieved.version_intent == 1


class TestAssemblyImmutability:
    @pytest.mark.asyncio
    async def test_validated_document_becomes_immutable(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        await repo.mark_completed(
            assembled_doc_id=assembled_doc.id,
            assembled_structure={"blocks": []},
            injection_results=[],
            validation_result={"is_valid": True},
            metadata={},
            headers=[],
            footers=[],
            total_blocks=0,
            dynamic_blocks_count=0,
            static_blocks_count=0,
            injected_sections_count=0,
            assembly_duration_ms=100.0,
            assembly_hash="final_hash",
        )

        validated = await repo.mark_validated(assembled_doc.id)

        assert validated is not None
        assert validated.is_immutable is True
        assert validated.status == AssemblyStatus.VALIDATED

    @pytest.mark.asyncio
    async def test_immutable_document_cannot_be_modified(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        await repo.mark_completed(
            assembled_doc_id=assembled_doc.id,
            assembled_structure={"blocks": []},
            injection_results=[],
            validation_result={"is_valid": True},
            metadata={},
            headers=[],
            footers=[],
            total_blocks=0,
            dynamic_blocks_count=0,
            static_blocks_count=0,
            injected_sections_count=0,
            assembly_duration_ms=100.0,
            assembly_hash="final_hash",
        )
        await repo.mark_validated(assembled_doc.id)

        result = await repo.mark_in_progress(assembled_doc.id)

        assert result.status == AssemblyStatus.VALIDATED
        assert result.is_immutable is True

    @pytest.mark.asyncio
    async def test_immutable_document_cannot_be_deleted(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        await repo.mark_completed(
            assembled_doc_id=assembled_doc.id,
            assembled_structure={"blocks": []},
            injection_results=[],
            validation_result={"is_valid": True},
            metadata={},
            headers=[],
            footers=[],
            total_blocks=0,
            dynamic_blocks_count=0,
            static_blocks_count=0,
            injected_sections_count=0,
            assembly_duration_ms=100.0,
            assembly_hash="final_hash",
        )
        await repo.mark_validated(assembled_doc.id)

        deleted = await repo.delete(assembled_doc.id)

        assert deleted is False
        still_exists = await repo.get_by_id(assembled_doc.id)
        assert still_exists is not None


class TestAssemblyStatePersistence:
    @pytest.mark.asyncio
    async def test_assembled_structure_persisted_correctly(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        assembled_structure = {
            "blocks": [
                {"block_id": "blk_001", "block_type": "paragraph", "content": "Test"},
                {"block_id": "blk_002", "block_type": "heading", "level": 1},
            ]
        }

        await repo.mark_completed(
            assembled_doc_id=assembled_doc.id,
            assembled_structure=assembled_structure,
            injection_results=[{"section_id": 1, "was_injected": True}],
            validation_result={"is_valid": True, "error_codes": []},
            metadata={"title": "Test Document"},
            headers=[{"type": "header", "content": "Header"}],
            footers=[{"type": "footer", "content": "Footer"}],
            total_blocks=2,
            dynamic_blocks_count=1,
            static_blocks_count=1,
            injected_sections_count=1,
            assembly_duration_ms=150.5,
            assembly_hash="final_hash_456",
        )

        retrieved = await repo.get_by_id(assembled_doc.id)

        assert retrieved.assembled_structure == assembled_structure
        assert retrieved.total_blocks == 2
        assert retrieved.dynamic_blocks_count == 1
        assert retrieved.static_blocks_count == 1
        assert retrieved.injected_sections_count == 1
        assert retrieved.assembly_duration_ms == 150.5
        assert retrieved.assembly_hash == "final_hash_456"

    @pytest.mark.asyncio
    async def test_failed_assembly_persists_error_info(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        await repo.mark_failed(
            assembled_doc_id=assembled_doc.id,
            error_code="MISSING_VALIDATED_CONTENT",
            error_message="Dynamic section 5 lacks validated content",
        )

        retrieved = await repo.get_by_id(assembled_doc.id)

        assert retrieved.status == AssemblyStatus.FAILED
        assert retrieved.error_code == "MISSING_VALIDATED_CONTENT"
        assert "Dynamic section 5" in retrieved.error_message


class TestQueryMethods:
    @pytest.mark.asyncio
    async def test_get_validated_by_document(
        self,
        db_session,
        document_id,
        template_version_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        for i in range(3):
            assembled_doc = await repo.create(
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=i + 1,
                section_output_batch_id=uuid4(),
                assembly_hash=f"hash_{i}",
            )
            await repo.mark_completed(
                assembled_doc_id=assembled_doc.id,
                assembled_structure={"blocks": []},
                injection_results=[],
                validation_result={"is_valid": True},
                metadata={},
                headers=[],
                footers=[],
                total_blocks=0,
                dynamic_blocks_count=0,
                static_blocks_count=0,
                injected_sections_count=0,
                assembly_duration_ms=100.0,
                assembly_hash=f"final_hash_{i}",
            )
            if i < 2:
                await repo.mark_validated(assembled_doc.id)

        validated = await repo.get_validated_by_document(document_id)

        assert len(validated) == 2

    @pytest.mark.asyncio
    async def test_exists_for_batch(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        exists_before = await repo.exists_for_batch(section_output_batch_id)
        assert exists_before is False

        await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        exists_after = await repo.exists_for_batch(section_output_batch_id)
        assert exists_after is True

    @pytest.mark.asyncio
    async def test_get_latest_by_document(
        self,
        db_session,
        document_id,
        template_version_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        for i in [1, 3, 2]:
            await repo.create(
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=i,
                section_output_batch_id=uuid4(),
                assembly_hash=f"hash_{i}",
            )

        latest = await repo.get_latest_by_document(document_id)

        assert latest is not None
        assert latest.version_intent == 3

    @pytest.mark.asyncio
    async def test_get_renderable_document(
        self,
        db_session,
        document_id,
        template_version_id,
        section_output_batch_id,
    ):
        repo = AssembledDocumentRepository(db_session)

        assembled_doc = await repo.create(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            section_output_batch_id=section_output_batch_id,
            assembly_hash="hash_123",
        )

        renderable = await repo.get_renderable_document(document_id, 1)
        assert renderable is None

        await repo.mark_completed(
            assembled_doc_id=assembled_doc.id,
            assembled_structure={"blocks": []},
            injection_results=[],
            validation_result={"is_valid": True},
            metadata={},
            headers=[],
            footers=[],
            total_blocks=0,
            dynamic_blocks_count=0,
            static_blocks_count=0,
            injected_sections_count=0,
            assembly_duration_ms=100.0,
            assembly_hash="final_hash",
        )
        await repo.mark_validated(assembled_doc.id)

        renderable = await repo.get_renderable_document(document_id, 1)
        assert renderable is not None
        assert renderable.can_be_rendered is True


class TestModelProperties:
    def test_is_complete_property(self):
        doc = AssembledDocument()
        doc.status = AssemblyStatus.PENDING
        assert doc.is_complete is False

        doc.status = AssemblyStatus.COMPLETED
        assert doc.is_complete is True

        doc.status = AssemblyStatus.VALIDATED
        assert doc.is_complete is True

    def test_is_failed_property(self):
        doc = AssembledDocument()
        doc.status = AssemblyStatus.PENDING
        assert doc.is_failed is False

        doc.status = AssemblyStatus.FAILED
        assert doc.is_failed is True

    def test_can_be_rendered_property(self):
        doc = AssembledDocument()
        doc.is_immutable = False
        doc.status = AssemblyStatus.PENDING
        doc.assembled_structure = {}
        assert doc.can_be_rendered is False

        doc.is_immutable = True
        doc.status = AssemblyStatus.VALIDATED
        doc.assembled_structure = {"blocks": []}
        assert doc.can_be_rendered is True
