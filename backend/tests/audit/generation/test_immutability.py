from datetime import datetime
from uuid import UUID, uuid4

import pytest

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.generation_schemas import GenerationAuditAction
from backend.app.domains.audit.repository import AuditRepository


@pytest.mark.asyncio
class TestImmutability:
    async def test_audit_record_timestamp_preserved(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        before_creation = datetime.utcnow()

        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        after_creation = datetime.utcnow()

        assert log.timestamp is not None
        assert before_creation <= log.timestamp <= after_creation

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].timestamp == log.timestamp

    async def test_audit_record_action_immutable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        original_action = log.action

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].action == original_action

    async def test_audit_record_metadata_immutable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        original_metadata = log.metadata_.copy()

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].metadata_ == original_metadata

    async def test_audit_record_entity_id_immutable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        original_entity_id = log.entity_id

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].entity_id == original_entity_id

    async def test_audit_record_entity_type_immutable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        original_entity_type = log.entity_type

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].entity_type == original_entity_type

    async def test_multiple_audit_records_remain_stable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        document_id: UUID,
        template_version_id: UUID,
    ):
        batch_id = uuid4()
        section_output_id = uuid4()

        log1 = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        log2 = await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        all_logs = await generation_audit_service.query_by_document_id(document_id)

        log1_retrieved = None
        log2_retrieved = None
        for log in all_logs:
            if log.id == log1.id:
                log1_retrieved = log
            elif log.id == log2.id:
                log2_retrieved = log

        assert log1_retrieved is not None
        assert log2_retrieved is not None
        assert log1_retrieved.action == log1.action
        assert log1_retrieved.timestamp == log1.timestamp
        assert log1_retrieved.metadata_ == log1.metadata_
        assert log2_retrieved.action == log2.action
        assert log2_retrieved.timestamp == log2.timestamp
        assert log2_retrieved.metadata_ == log2.metadata_

    async def test_failure_record_immutable(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
    ):
        error_code = "GENERATION_TIMEOUT"
        error_message = "Section generation timed out after 30s"

        await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            error_code=error_code,
            error_message=error_message,
        )

        retrieved_logs = await audit_repository.query(entity_id=section_output_id)
        assert len(retrieved_logs) == 1

        retrieved = retrieved_logs[0]
        assert retrieved.action == GenerationAuditAction.SECTION_GENERATION_FAILED.value
        assert retrieved.metadata_["error_code"] == error_code
        assert retrieved.metadata_["error_message"] == error_message

    async def test_audit_history_stable_after_additional_operations(
        self,
        generation_audit_service: GenerationAuditService,
        document_id: UUID,
        template_version_id: UUID,
    ):
        batch_id = uuid4()
        initial_logs = await generation_audit_service.query_by_document_id(document_id)
        initial_count = len(initial_logs)
        initial_timestamps = [log.timestamp for log in initial_logs]
        initial_actions = [log.action for log in initial_logs]

        section_output_id = uuid4()
        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        all_logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(all_logs) == initial_count + 1

        for i, initial_timestamp in enumerate(initial_timestamps):
            matching_log = next(
                (
                    log
                    for log in all_logs
                    if log.action == initial_actions[i] and log.timestamp == initial_timestamp
                ),
                None,
            )
            assert matching_log is not None

    async def test_audit_log_id_uniqueness_preserved(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
    ):
        document_id = uuid4()
        template_version_id = uuid4()

        logs = []
        for i in range(5):
            batch_id = uuid4()
            log = await generation_audit_service.log_generation_initiated(
                batch_id=batch_id,
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=i + 1,
                total_sections=1,
            )
            logs.append(log)

        log_ids = [log.id for log in logs]
        assert len(log_ids) == len(set(log_ids))

        all_logs = await generation_audit_service.query_by_document_id(document_id)
        retrieved_ids = [log.id for log in all_logs]

        for original_id in log_ids:
            assert original_id in retrieved_ids
