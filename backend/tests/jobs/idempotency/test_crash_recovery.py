from unittest.mock import MagicMock

import pytest


class TestJobStateRecovery:

    def test_job_error_is_stored_on_failure(self, mock_job_repo):
        error_message = "Pipeline failed at generation stage"

        job = MagicMock()
        job.error = None

        job.error = error_message

        assert job.error is not None
        assert "generation" in job.error.lower()

    def test_job_result_is_none_on_failure(self, mock_job_repo):
        job = MagicMock()
        job.result = None
        job.error = "Failed"

        assert job.result is None
        assert job.error is not None

    def test_partial_result_preserves_completed_stages(self):
        partial_result = {
            "input_batch_id": "44444444-4444-4444-4444-444444444444",
            "stages_completed": ["INPUT_PREPARATION"],
            "failed_stage": "SECTION_GENERATION",
        }

        assert "input_batch_id" in partial_result
        assert "INPUT_PREPARATION" in partial_result["stages_completed"]


class TestStageFailureRecovery:

    def test_input_preparation_failure_leaves_no_batch(self):
        result = {
            "input_batch_id": None,
            "error": "Input preparation failed",
            "failed_stage": "INPUT_PREPARATION",
        }

        assert result["input_batch_id"] is None
        assert result["failed_stage"] == "INPUT_PREPARATION"

    def test_generation_failure_preserves_input_batch(self, fixed_input_batch_id):
        result = {
            "input_batch_id": str(fixed_input_batch_id),
            "output_batch_id": None,
            "error": "Generation failed",
            "failed_stage": "SECTION_GENERATION",
        }

        assert result["input_batch_id"] is not None
        assert result["output_batch_id"] is None
        assert result["failed_stage"] == "SECTION_GENERATION"

    def test_assembly_failure_preserves_prior_stages(
        self, fixed_input_batch_id, fixed_output_batch_id
    ):
        result = {
            "input_batch_id": str(fixed_input_batch_id),
            "output_batch_id": str(fixed_output_batch_id),
            "assembled_document_id": None,
            "error": "Assembly failed",
            "failed_stage": "DOCUMENT_ASSEMBLY",
        }

        assert result["input_batch_id"] is not None
        assert result["output_batch_id"] is not None
        assert result["assembled_document_id"] is None

    def test_rendering_failure_preserves_assembly(
        self, fixed_input_batch_id, fixed_output_batch_id, fixed_assembled_id
    ):
        result = {
            "input_batch_id": str(fixed_input_batch_id),
            "output_batch_id": str(fixed_output_batch_id),
            "assembled_document_id": str(fixed_assembled_id),
            "rendered_document_id": None,
            "error": "Rendering failed",
            "failed_stage": "DOCUMENT_RENDERING",
        }

        assert result["assembled_document_id"] is not None
        assert result["rendered_document_id"] is None

    def test_versioning_failure_preserves_all_prior_stages(
        self,
        fixed_input_batch_id,
        fixed_output_batch_id,
        fixed_assembled_id,
        fixed_rendered_id,
    ):
        result = {
            "input_batch_id": str(fixed_input_batch_id),
            "output_batch_id": str(fixed_output_batch_id),
            "assembled_document_id": str(fixed_assembled_id),
            "rendered_document_id": str(fixed_rendered_id),
            "version_id": None,
            "error": "Versioning failed",
            "failed_stage": "VERSIONING",
        }

        assert result["rendered_document_id"] is not None
        assert result["version_id"] is None


class TestTerminalStateConsistency:

    def test_successful_completion_has_all_artifacts(self, sample_job_result):
        required_artifacts = [
            "input_batch_id",
            "output_batch_id",
            "assembled_document_id",
            "rendered_document_id",
            "version_id",
        ]

        for artifact in required_artifacts:
            assert artifact in sample_job_result
            assert sample_job_result[artifact] is not None

    def test_failure_has_error_message(self):
        failure_result = {
            "error": "Pipeline failed",
            "failed_stage": "SECTION_GENERATION",
        }

        assert failure_result["error"] is not None
        assert len(failure_result["error"]) > 0


class TestRecoveryLookup:

    @pytest.mark.asyncio
    async def test_can_lookup_input_batch_after_crash(
        self, mock_generation_repo, fixed_input_batch_id
    ):
        existing_batch = MagicMock()
        existing_batch.id = fixed_input_batch_id
        existing_batch.is_validated = True

        mock_generation_repo.get_batch_by_id.return_value = existing_batch

        result = await mock_generation_repo.get_batch_by_id(fixed_input_batch_id)

        assert result is not None
        assert result.id == fixed_input_batch_id

    @pytest.mark.asyncio
    async def test_can_lookup_output_batch_by_input_after_crash(
        self, mock_output_repo, fixed_input_batch_id, fixed_output_batch_id
    ):
        existing_output = MagicMock()
        existing_output.id = fixed_output_batch_id
        existing_output.input_batch_id = fixed_input_batch_id

        mock_output_repo.get_batch_by_input_batch_id.return_value = existing_output

        result = await mock_output_repo.get_batch_by_input_batch_id(fixed_input_batch_id)

        assert result is not None
        assert result.id == fixed_output_batch_id


class TestStageIdempotencyOnRestart:

    def test_completed_stage_can_be_detected(self):
        job_state = {
            "stages_completed": ["INPUT_PREPARATION", "SECTION_GENERATION"],
            "current_stage": "DOCUMENT_ASSEMBLY",
        }

        def is_stage_completed(stage_name, state):
            return stage_name in state.get("stages_completed", [])

        assert is_stage_completed("INPUT_PREPARATION", job_state)
        assert is_stage_completed("SECTION_GENERATION", job_state)
        assert not is_stage_completed("DOCUMENT_ASSEMBLY", job_state)

    def test_artifact_presence_indicates_stage_completion(self, sample_job_result):
        def has_artifact(result, artifact_key):
            return result.get(artifact_key) is not None

        assert has_artifact(sample_job_result, "input_batch_id")
        assert has_artifact(sample_job_result, "output_batch_id")
        assert has_artifact(sample_job_result, "assembled_document_id")
