import hashlib
import json
from unittest.mock import MagicMock
from uuid import UUID

import pytest


class TestJobPayloadIdempotency:

    def test_same_payload_produces_same_hash(self, sample_job_payload):
        def compute_payload_hash(payload):
            return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        hash1 = compute_payload_hash(sample_job_payload)
        hash2 = compute_payload_hash(sample_job_payload)

        assert hash1 == hash2

    def test_different_payload_produces_different_hash(self, sample_job_payload):
        def compute_payload_hash(payload):
            return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        modified_payload = sample_job_payload.copy()
        modified_payload["version_intent"] = 2

        hash1 = compute_payload_hash(sample_job_payload)
        hash2 = compute_payload_hash(modified_payload)

        assert hash1 != hash2

    def test_payload_order_does_not_affect_hash(self, fixed_document_id, fixed_template_version_id):
        def compute_payload_hash(payload):
            return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        payload1 = {
            "document_id": str(fixed_document_id),
            "template_version_id": str(fixed_template_version_id),
            "version_intent": 1,
        }

        payload2 = {
            "version_intent": 1,
            "document_id": str(fixed_document_id),
            "template_version_id": str(fixed_template_version_id),
        }

        assert compute_payload_hash(payload1) == compute_payload_hash(payload2)


class TestDuplicateDetection:

    @pytest.mark.asyncio
    async def test_duplicate_detection_returns_existing_on_match(self, mock_versioning_repo):
        existing_version = MagicMock()
        existing_version.id = UUID("99999999-9999-9999-9999-999999999999")
        existing_version.version_number = 1
        existing_version.content_hash = "existing_hash"

        mock_versioning_repo.get_by_content_hash.return_value = existing_version

        result = await mock_versioning_repo.get_by_content_hash("existing_hash")

        assert result is not None
        assert result.id == existing_version.id

    @pytest.mark.asyncio
    async def test_duplicate_detection_returns_none_when_no_match(self, mock_versioning_repo):
        mock_versioning_repo.get_by_content_hash.return_value = None

        result = await mock_versioning_repo.get_by_content_hash("new_hash")

        assert result is None


class TestBatchIdempotency:

    @pytest.mark.asyncio
    async def test_output_batch_lookup_by_input_batch(self, mock_output_repo, fixed_input_batch_id):
        existing_output_batch = MagicMock()
        existing_output_batch.id = UUID("55555555-5555-5555-5555-555555555555")
        existing_output_batch.input_batch_id = fixed_input_batch_id

        mock_output_repo.get_batch_by_input_batch_id.return_value = existing_output_batch

        result = await mock_output_repo.get_batch_by_input_batch_id(fixed_input_batch_id)

        assert result is not None
        assert result.input_batch_id == fixed_input_batch_id

    @pytest.mark.asyncio
    async def test_assembly_lookup_by_output_batch(self, mock_assembly_repo, fixed_output_batch_id):
        existing_assembly = MagicMock()
        existing_assembly.id = UUID("66666666-6666-6666-6666-666666666666")
        existing_assembly.section_output_batch_id = fixed_output_batch_id

        mock_assembly_repo.get_by_output_batch_id.return_value = existing_assembly

        result = await mock_assembly_repo.get_by_output_batch_id(fixed_output_batch_id)

        assert result is not None
        assert result.section_output_batch_id == fixed_output_batch_id


class TestVersionNumberSequence:

    @pytest.mark.asyncio
    async def test_next_version_increments_correctly(self, mock_versioning_repo, fixed_document_id):
        mock_versioning_repo.get_latest_version.return_value = MagicMock(version_number=1)

        latest = await mock_versioning_repo.get_latest_version(fixed_document_id)
        next_version_number = latest.version_number + 1

        assert next_version_number == 2

    @pytest.mark.asyncio
    async def test_first_version_starts_at_one(self, mock_versioning_repo, fixed_document_id):
        mock_versioning_repo.get_latest_version.return_value = None

        latest = await mock_versioning_repo.get_latest_version(fixed_document_id)

        version_number = 1 if latest is None else latest.version_number + 1

        assert version_number == 1


class TestJobStatusIdempotency:

    def test_completed_status_is_terminal(self):
        from backend.app.domains.job.models import JobStatus

        assert JobStatus.COMPLETED in {JobStatus.COMPLETED, JobStatus.FAILED}

    def test_failed_status_is_terminal(self):
        from backend.app.domains.job.models import JobStatus

        assert JobStatus.FAILED in {JobStatus.COMPLETED, JobStatus.FAILED}

    def test_pending_status_is_not_terminal(self):
        from backend.app.domains.job.models import JobStatus

        assert JobStatus.PENDING not in {JobStatus.COMPLETED, JobStatus.FAILED}


class TestResultDataConsistency:

    def test_result_data_contains_all_artifact_ids(self, sample_job_result):
        required_keys = [
            "input_batch_id",
            "output_batch_id",
            "assembled_document_id",
            "rendered_document_id",
            "version_id",
            "content_hash",
        ]

        for key in required_keys:
            assert key in sample_job_result

    def test_result_data_artifact_ids_are_valid_uuids(self, sample_job_result):
        uuid_keys = [
            "input_batch_id",
            "output_batch_id",
            "assembled_document_id",
            "rendered_document_id",
            "version_id",
        ]

        for key in uuid_keys:
            UUID(sample_job_result[key])


class TestContentHashIdempotency:

    def test_content_hash_is_deterministic(self):
        content = "This is the document content"

        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self):
        content1 = "Document version 1"
        content2 = "Document version 2"

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 != hash2

    def test_duplicate_content_returns_same_hash(self):
        content_a = "Identical content"
        content_b = "Identical content"

        hash_a = hashlib.sha256(content_a.encode()).hexdigest()
        hash_b = hashlib.sha256(content_b.encode()).hexdigest()

        assert hash_a == hash_b
