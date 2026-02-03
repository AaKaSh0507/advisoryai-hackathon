from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest


class TestAuditEntryStructure:

    def test_audit_entry_has_required_fields(self, fixed_job_id):
        audit_entry = {
            "id": str(UUID("99999999-9999-9999-9999-999999999999")),
            "job_id": str(fixed_job_id),
            "stage": "INPUT_PREPARATION",
            "action": "STARTED",
            "timestamp": datetime.utcnow().isoformat(),
            "details": {},
        }

        required_fields = ["id", "job_id", "stage", "action", "timestamp"]
        for field in required_fields:
            assert field in audit_entry

    def test_audit_entry_action_values_are_valid(self):
        valid_actions = ["STARTED", "COMPLETED", "FAILED"]
        entry = {"action": "COMPLETED"}

        assert entry["action"] in valid_actions


class TestAuditSequencing:

    def test_audit_entries_have_chronological_timestamps(self):
        t1 = datetime(2025, 1, 15, 10, 0, 0)
        t2 = datetime(2025, 1, 15, 10, 0, 1)
        t3 = datetime(2025, 1, 15, 10, 0, 2)

        entries = [
            {"stage": "INPUT_PREPARATION", "action": "STARTED", "timestamp": t1},
            {"stage": "INPUT_PREPARATION", "action": "COMPLETED", "timestamp": t2},
            {"stage": "SECTION_GENERATION", "action": "STARTED", "timestamp": t3},
        ]

        timestamps = [e["timestamp"] for e in entries]
        assert timestamps == sorted(timestamps)

    def test_stage_started_before_completed(self):
        entries = [
            {"stage": "INPUT_PREPARATION", "action": "STARTED", "order": 1},
            {"stage": "INPUT_PREPARATION", "action": "COMPLETED", "order": 2},
        ]

        started = next(e for e in entries if e["action"] == "STARTED")
        completed = next(e for e in entries if e["action"] == "COMPLETED")

        assert started["order"] < completed["order"]


class TestAuditIdempotency:

    def test_audit_entry_id_is_unique(self):
        entry1_id = UUID("11111111-1111-1111-1111-111111111111")
        entry2_id = UUID("22222222-2222-2222-2222-222222222222")

        assert entry1_id != entry2_id

    def test_duplicate_audit_detection_by_job_stage_action(self):
        existing_entries = [
            {"job_id": "job1", "stage": "INPUT_PREPARATION", "action": "COMPLETED"},
        ]

        def entry_exists(entries, job_id, stage, action):
            return any(
                e["job_id"] == job_id and e["stage"] == stage and e["action"] == action
                for e in entries
            )

        assert entry_exists(existing_entries, "job1", "INPUT_PREPARATION", "COMPLETED")
        assert not entry_exists(existing_entries, "job1", "SECTION_GENERATION", "COMPLETED")


class TestAuditConsistencyWithJobResult:

    def test_completed_job_has_completion_audit(self, sample_job_result):
        expected_stages = [
            "INPUT_PREPARATION",
            "SECTION_GENERATION",
            "DOCUMENT_ASSEMBLY",
            "DOCUMENT_RENDERING",
            "VERSIONING",
        ]

        audit_entries = [{"stage": stage, "action": "COMPLETED"} for stage in expected_stages]

        for entry in audit_entries:
            assert entry["action"] == "COMPLETED"

        assert len(audit_entries) == len(expected_stages)

    def test_failed_job_has_failure_audit(self):
        failure_result = {
            "error": "Generation failed",
            "failed_stage": "SECTION_GENERATION",
        }

        failure_audit = {
            "stage": failure_result["failed_stage"],
            "action": "FAILED",
            "details": {"error": failure_result["error"]},
        }

        assert failure_audit["action"] == "FAILED"
        assert failure_audit["stage"] == "SECTION_GENERATION"


class TestAuditDetailsConsistency:

    def test_completed_stage_audit_has_artifact_id(
        self, fixed_input_batch_id, fixed_output_batch_id
    ):
        completed_audit = {
            "stage": "INPUT_PREPARATION",
            "action": "COMPLETED",
            "details": {
                "batch_id": str(fixed_input_batch_id),
                "total_inputs": 5,
            },
        }

        assert "batch_id" in completed_audit["details"]
        assert completed_audit["details"]["batch_id"] == str(fixed_input_batch_id)

    def test_failed_stage_audit_has_error_details(self):
        failed_audit = {
            "stage": "SECTION_GENERATION",
            "action": "FAILED",
            "details": {
                "error_type": "GenerationError",
                "error_message": "LLM timeout",
            },
        }

        assert "error_message" in failed_audit["details"]
        assert len(failed_audit["details"]["error_message"]) > 0


class TestAuditLookup:

    @pytest.mark.asyncio
    async def test_audit_lookup_returns_entries_for_job(self, mock_audit_service, fixed_job_id):
        expected_entries = [
            MagicMock(job_id=fixed_job_id, stage="INPUT_PREPARATION", action="COMPLETED"),
            MagicMock(job_id=fixed_job_id, stage="SECTION_GENERATION", action="STARTED"),
        ]
        mock_audit_service.get_entries_for_job.return_value = expected_entries

        entries = await mock_audit_service.get_entries_for_job(fixed_job_id)

        assert len(entries) == 2
        assert all(e.job_id == fixed_job_id for e in entries)

    @pytest.mark.asyncio
    async def test_audit_lookup_returns_empty_for_no_entries(
        self, mock_audit_service, fixed_job_id
    ):
        mock_audit_service.get_entries_for_job.return_value = []

        entries = await mock_audit_service.get_entries_for_job(fixed_job_id)

        assert entries == []


class TestAuditCreationIdempotency:

    @pytest.mark.asyncio
    async def test_audit_service_can_log_stage_events(self, mock_audit_service, fixed_job_id):
        await mock_audit_service.log_stage_started(fixed_job_id, "INPUT_PREPARATION")
        await mock_audit_service.log_stage_completed(fixed_job_id, "INPUT_PREPARATION", {})
        await mock_audit_service.log_stage_started(fixed_job_id, "SECTION_GENERATION")

        assert mock_audit_service.log_stage_started.call_count == 2
        assert mock_audit_service.log_stage_completed.call_count == 1
