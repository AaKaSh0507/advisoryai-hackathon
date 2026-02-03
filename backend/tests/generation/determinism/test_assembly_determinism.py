from uuid import UUID

from backend.app.domains.assembly.schemas import AssemblyRequest, AssemblyResult, compute_text_hash


class TestAssemblyHashDeterminism:

    def test_text_hash_is_deterministic(self):
        text = "Sample content for hashing"
        hash1 = compute_text_hash(text)
        hash2 = compute_text_hash(text)
        assert hash1 == hash2

    def test_different_text_produces_different_hash(self):
        hash1 = compute_text_hash("Content A")
        hash2 = compute_text_hash("Content B")
        assert hash1 != hash2

    def test_hash_format_is_consistent(self):
        hash_value = compute_text_hash("Test content")
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_empty_string_has_consistent_hash(self):
        hash1 = compute_text_hash("")
        hash2 = compute_text_hash("")
        assert hash1 == hash2

    def test_whitespace_affects_hash(self):
        hash1 = compute_text_hash("content")
        hash2 = compute_text_hash(" content")
        assert hash1 != hash2


class TestAssemblyRequestDeterminism:

    def test_assembly_request_parameters_are_consistent(self):
        fixed_document_id = UUID("11111111-1111-1111-1111-111111111111")
        fixed_template_version_id = UUID("22222222-2222-2222-2222-222222222222")
        fixed_output_batch_id = UUID("33333333-3333-3333-3333-333333333333")

        request1 = AssemblyRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            section_output_batch_id=fixed_output_batch_id,
            version_intent=1,
        )

        request2 = AssemblyRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            section_output_batch_id=fixed_output_batch_id,
            version_intent=1,
        )

        assert request1.document_id == request2.document_id
        assert request1.template_version_id == request2.template_version_id
        assert request1.section_output_batch_id == request2.section_output_batch_id
        assert request1.version_intent == request2.version_intent

    def test_different_version_intent_creates_different_request(self):
        fixed_document_id = UUID("11111111-1111-1111-1111-111111111111")
        fixed_template_version_id = UUID("22222222-2222-2222-2222-222222222222")
        fixed_output_batch_id = UUID("33333333-3333-3333-3333-333333333333")

        request1 = AssemblyRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            section_output_batch_id=fixed_output_batch_id,
            version_intent=1,
        )

        request2 = AssemblyRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            section_output_batch_id=fixed_output_batch_id,
            version_intent=2,
        )

        assert request1.version_intent != request2.version_intent


class TestAssemblyResultConsistency:

    def test_assembly_result_for_failure_is_predictable(self):
        result = AssemblyResult(
            success=False,
            assembled_document=None,
            error_message="Assembly failed: missing blocks",
        )

        assert result.success is False
        assert result.assembled_document is None
        assert result.error_message is not None

    def test_failed_assembly_result_has_error(self):
        result = AssemblyResult(
            success=False,
            assembled_document=None,
            error_message="Assembly failed: missing blocks",
        )

        assert result.success is False
        assert result.assembled_document is None
        assert result.error_message is not None

    def test_result_defaults_are_consistent(self):
        result1 = AssemblyResult(success=False, error_message="Error")
        result2 = AssemblyResult(success=False, error_message="Error")

        assert result1.success == result2.success
        assert result1.assembled_document == result2.assembled_document
