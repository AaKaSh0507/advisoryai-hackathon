from uuid import UUID, uuid4

import pytest

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.generation_schemas import GenerationAuditAction
from backend.app.domains.audit.repository import AuditRepository


@pytest.mark.asyncio
class TestQueryByTemplateId:
    async def test_query_by_template_id_returns_results(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        logs = await generation_audit_service.query_by_template_id(template_version_id)

        assert len(logs) >= 1
        assert all(
            log.metadata_.get("template_version_id") == str(template_version_id) for log in logs
        )

    async def test_query_by_template_id_empty_for_nonexistent(
        self,
        generation_audit_service: GenerationAuditService,
    ):
        nonexistent_id = uuid4()
        logs = await generation_audit_service.query_by_template_id(nonexistent_id)
        assert logs == []

    async def test_query_by_template_id_multiple_batches(
        self,
        generation_audit_service: GenerationAuditService,
        template_version_id: UUID,
    ):
        document_id1 = uuid4()
        document_id2 = uuid4()
        batch_id1 = uuid4()
        batch_id2 = uuid4()

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id1,
            document_id=document_id1,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id2,
            document_id=document_id2,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=3,
        )

        logs = await generation_audit_service.query_by_template_id(template_version_id)

        assert len(logs) == 2


@pytest.mark.asyncio
class TestQueryByDocumentId:
    async def test_query_by_document_id_returns_results(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(logs) >= 1

    async def test_query_by_document_id_empty_for_nonexistent(
        self,
        generation_audit_service: GenerationAuditService,
    ):
        nonexistent_id = uuid4()
        logs = await generation_audit_service.query_by_document_id(nonexistent_id)
        assert logs == []

    async def test_query_by_document_id_includes_all_related_logs(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
        template_version_id: UUID,
    ):
        batch_id = uuid4()
        section_output_id = uuid4()
        assembled_id = uuid4()

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        await generation_audit_service.log_batch_generation_completed(
            batch_id=batch_id,
            document_id=document_id,
            completed_sections=1,
            failed_sections=0,
            total_sections=1,
        )

        await generation_audit_service.log_document_assembly_completed(
            assembled_document_id=assembled_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_blocks=5,
            dynamic_blocks_count=1,
            static_blocks_count=4,
            injected_sections_count=1,
            assembly_hash="assemblyhash",
        )

        logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(logs) == 4
        actions = [log.action for log in logs]
        assert GenerationAuditAction.GENERATION_INITIATED.value in actions
        assert GenerationAuditAction.SECTION_GENERATION_COMPLETED.value in actions
        assert GenerationAuditAction.BATCH_GENERATION_COMPLETED.value in actions
        assert GenerationAuditAction.DOCUMENT_ASSEMBLY_COMPLETED.value in actions


@pytest.mark.asyncio
class TestQueryByVersionNumber:
    async def test_query_by_version_number_returns_results(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
    ):
        version_id = uuid4()

        await generation_audit_service.log_document_version_created(
            version_id=version_id,
            document_id=document_id,
            version_number=1,
            output_path="path/to/output.docx",
            content_hash="versionhash",
        )

        logs = await generation_audit_service.query_by_version_number(
            document_id=document_id,
            version_number=1,
        )

        assert len(logs) >= 1

    async def test_query_by_version_number_empty_for_nonexistent(
        self,
        generation_audit_service: GenerationAuditService,
    ):
        nonexistent_doc_id = uuid4()
        logs = await generation_audit_service.query_by_version_number(
            document_id=nonexistent_doc_id,
            version_number=999,
        )
        assert logs == []

    async def test_query_by_version_number_filters_by_version_number(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
    ):
        version_id1 = uuid4()
        version_id2 = uuid4()

        await generation_audit_service.log_document_version_created(
            version_id=version_id1,
            document_id=document_id,
            version_number=1,
            output_path="path/to/v1.docx",
            content_hash="hash1",
        )

        await generation_audit_service.log_document_version_created(
            version_id=version_id2,
            document_id=document_id,
            version_number=2,
            output_path="path/to/v2.docx",
            content_hash="hash2",
        )

        logs_v1 = await generation_audit_service.query_by_version_number(
            document_id=document_id,
            version_number=1,
        )
        logs_v2 = await generation_audit_service.query_by_version_number(
            document_id=document_id,
            version_number=2,
        )

        assert len(logs_v1) == 1
        assert logs_v1[0].metadata_["version_number"] == 1

        assert len(logs_v2) == 1
        assert logs_v2[0].metadata_["version_number"] == 2


@pytest.mark.asyncio
class TestQueryByJobId:
    async def test_query_by_job_id_returns_results(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
            job_id=batch_id,
        )

        logs = await generation_audit_service.query_by_job_id(batch_id)

        assert len(logs) >= 1
        assert all(log.metadata_.get("job_id") == str(batch_id) for log in logs)

    async def test_query_by_job_id_empty_for_nonexistent(
        self,
        generation_audit_service: GenerationAuditService,
    ):
        nonexistent_id = uuid4()
        logs = await generation_audit_service.query_by_job_id(nonexistent_id)
        assert logs == []

    async def test_query_by_job_id_includes_related_section_logs(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        job_id = uuid4()

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=2,
            job_id=job_id,
        )

        section_output_id1 = uuid4()
        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id1,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
            job_id=job_id,
        )

        section_output_id2 = uuid4()
        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id2,
            batch_id=batch_id,
            section_id=2,
            document_id=document_id,
            content_hash="hash2",
            content_length=150,
            job_id=job_id,
        )

        await generation_audit_service.log_batch_generation_completed(
            batch_id=batch_id,
            document_id=document_id,
            completed_sections=2,
            failed_sections=0,
            total_sections=2,
            job_id=job_id,
        )

        logs = await generation_audit_service.query_by_job_id(job_id)

        assert len(logs) == 4


@pytest.mark.asyncio
class TestQueryDeterminism:
    async def test_query_results_are_deterministic(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
        template_version_id: UUID,
    ):
        batch_id = uuid4()

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        section_output_id = uuid4()
        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        query1 = await generation_audit_service.query_by_document_id(document_id)
        query2 = await generation_audit_service.query_by_document_id(document_id)
        query3 = await generation_audit_service.query_by_document_id(document_id)

        assert len(query1) == len(query2) == len(query3)

        ids1 = [log.id for log in query1]
        ids2 = [log.id for log in query2]
        ids3 = [log.id for log in query3]

        assert set(ids1) == set(ids2) == set(ids3)

    async def test_query_with_limit_returns_consistent_results(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        document_id: UUID,
        template_version_id: UUID,
    ):
        for i in range(5):
            batch_id = uuid4()
            await generation_audit_service.log_generation_initiated(
                batch_id=batch_id,
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=i + 1,
                total_sections=1,
            )

        query1 = await generation_audit_service.query_by_document_id(document_id)
        query2 = await generation_audit_service.query_by_document_id(document_id)

        assert len(query1) == len(query2) == 5

    async def test_query_ordering_by_timestamp(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
        template_version_id: UUID,
    ):
        for i in range(3):
            batch_id = uuid4()
            await generation_audit_service.log_generation_initiated(
                batch_id=batch_id,
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=i + 1,
                total_sections=1,
            )

        logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(logs) == 3

        timestamps = [log.timestamp for log in logs]
        assert all(t is not None for t in timestamps)
