import hashlib
from typing import Any
from uuid import UUID

from backend.app.domains.generation.llm_client import BaseLLMClient
from backend.app.domains.generation.models import GenerationInput, GenerationInputBatch
from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.section_output_errors import (
    BatchNotFoundError,
    BatchNotValidatedError,
    DuplicateOutputBatchError,
)
from backend.app.domains.generation.section_output_models import (
    FailureCategory,
    SectionGenerationStatus,
    SectionOutput,
    SectionOutputBatch,
)
from backend.app.domains.generation.section_output_repository import SectionOutputRepository
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ExecuteSectionGenerationRequest,
    ExecuteSectionGenerationResponse,
    LLMInvocationRequest,
    SectionGenerationResult,
    SectionOutputResponse,
)
from backend.app.domains.generation.validation_schemas import (
    FailureType,
    QualityCheckConfig,
    RetryPolicy,
    StructuralValidationConfig,
)
from backend.app.domains.generation.validation_service import GenerationValidationService
from backend.app.infrastructure.datetime_utils import utc_now
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.generation.section_output_service")


class SectionGenerationService:
    def __init__(
        self,
        output_repo: SectionOutputRepository,
        input_repo: GenerationInputRepository,
        llm_client: BaseLLMClient,
        retry_policy: RetryPolicy | None = None,
        structural_config: StructuralValidationConfig | None = None,
        quality_config: QualityCheckConfig | None = None,
    ):
        self.output_repo = output_repo
        self.input_repo = input_repo
        self.llm_client = llm_client
        self.retry_policy = retry_policy or RetryPolicy()
        self.structural_config = structural_config
        self.quality_config = quality_config

    def _create_validation_service(
        self,
        constraints: ContentConstraints,
    ) -> GenerationValidationService:
        return GenerationValidationService(
            min_length=constraints.min_length,
            max_length=constraints.max_length,
            structural_config=self.structural_config,
            quality_config=self.quality_config,
            retry_policy=self.retry_policy,
        )

    async def execute_section_generation(
        self,
        request: ExecuteSectionGenerationRequest,
    ) -> ExecuteSectionGenerationResponse:
        logger.info(f"Starting section generation for input batch {request.input_batch_id}")

        input_batch = await self._get_validated_input_batch(request.input_batch_id)

        existing_output_batch = await self.output_repo.get_batch_by_input_batch_id(
            request.input_batch_id
        )
        if existing_output_batch:
            raise DuplicateOutputBatchError(request.input_batch_id)

        output_batch = await self._create_output_batch(input_batch)
        await self.output_repo.mark_batch_in_progress(output_batch.id)

        pending_outputs = await self._create_pending_outputs(output_batch, input_batch.inputs)

        results = await self._execute_generation_for_all_sections(
            pending_outputs,
            input_batch.inputs,
            request.constraints,
        )

        completed_count = sum(1 for r in results if r.status in ("COMPLETED", "VALIDATED"))
        failed_count = sum(1 for r in results if r.status == "FAILED")

        await self.output_repo.update_batch_progress(
            output_batch.id,
            completed_count,
            failed_count,
        )

        refreshed_batch = await self.output_repo.get_batch_by_id(
            output_batch.id, include_outputs=True
        )
        if refreshed_batch is None:
            raise RuntimeError(f"Failed to retrieve output batch {output_batch.id}")

        logger.info(
            f"Completed section generation for batch {output_batch.id}: "
            f"{completed_count} completed, {failed_count} failed"
        )

        return self._build_response(refreshed_batch)

    async def _get_validated_input_batch(self, batch_id: UUID) -> GenerationInputBatch:
        input_batch = await self.input_repo.get_batch_by_id(batch_id, include_inputs=True)
        if not input_batch:
            raise BatchNotFoundError(batch_id)

        if not input_batch.is_validated or not input_batch.is_immutable:
            raise BatchNotValidatedError(batch_id)

        return input_batch

    async def _create_output_batch(self, input_batch: GenerationInputBatch) -> SectionOutputBatch:
        batch = SectionOutputBatch(
            input_batch_id=input_batch.id,
            document_id=input_batch.document_id,
            version_intent=input_batch.version_intent,
            status=SectionGenerationStatus.PENDING,
            total_sections=len(input_batch.inputs),
            completed_sections=0,
            failed_sections=0,
            is_immutable=False,
        )
        return await self.output_repo.create_batch(batch)

    async def _create_pending_outputs(
        self,
        batch: SectionOutputBatch,
        inputs: list[GenerationInput],
    ) -> list[SectionOutput]:
        outputs = []
        for inp in inputs:
            output = SectionOutput(
                batch_id=batch.id,
                generation_input_id=inp.id,
                section_id=inp.section_id,
                sequence_order=inp.sequence_order,
                status=SectionGenerationStatus.PENDING,
                generation_metadata={},
                is_immutable=False,
            )
            outputs.append(output)

        created_outputs: list[SectionOutput] = await self.output_repo.create_outputs(outputs)
        return created_outputs

    async def _execute_generation_for_all_sections(
        self,
        outputs: list[SectionOutput],
        inputs: list[GenerationInput],
        constraints: ContentConstraints,
    ) -> list[SectionGenerationResult]:
        input_map = {inp.id: inp for inp in inputs}
        results: list[SectionGenerationResult] = []

        for output in outputs:
            gen_input = input_map.get(output.generation_input_id)
            if not gen_input:
                result = await self._handle_missing_input(output)
            else:
                result = await self._execute_single_section_generation(
                    output, gen_input, constraints
                )
            results.append(result)

        return results

    async def _execute_single_section_generation(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        constraints: ContentConstraints,
    ) -> SectionGenerationResult:
        validation_service = self._create_validation_service(constraints)
        current_attempt = output.retry_count or 0

        while current_attempt <= self.retry_policy.max_retries:
            try:
                result = await self._attempt_generation(
                    output,
                    gen_input,
                    constraints,
                    validation_service,
                    current_attempt,
                )

                if result.status in ("COMPLETED", "VALIDATED"):
                    return result

                if result.error_code and not self._is_retryable_error(
                    result.error_code,
                    current_attempt,
                ):
                    return result

                current_attempt += 1
                if current_attempt > self.retry_policy.max_retries:
                    return await self._handle_retry_exhaustion(
                        output,
                        gen_input,
                        result.error_message or "Max retries exceeded",
                        current_attempt - 1,
                    )

                await self._record_retry_attempt(
                    output,
                    result.error_code or "UNKNOWN",
                    result.error_message or "Unknown error",
                    current_attempt - 1,
                )

            except Exception as e:
                logger.error(
                    f"Unexpected error generating section {gen_input.section_id}: {e}",
                    exc_info=True,
                )
                return await self._handle_unexpected_error(output, gen_input, str(e))

        return await self._handle_retry_exhaustion(
            output,
            gen_input,
            "Max retries exceeded without success",
            current_attempt,
        )

    async def _attempt_generation(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        constraints: ContentConstraints,
        validation_service: GenerationValidationService,
        attempt_number: int,
    ) -> SectionGenerationResult:
        prompt_text = self._assemble_prompt(gen_input)

        invocation_request = LLMInvocationRequest(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            prompt_text=prompt_text,
            constraints=constraints,
        )

        llm_result = await self.llm_client.invoke(invocation_request)

        if not llm_result.is_successful:
            return await self._handle_llm_failure(
                output,
                gen_input,
                llm_result.error_message,
                attempt_number,
            )

        validation_result = validation_service.validate_content(llm_result.raw_output)

        if not validation_result.is_valid:
            return await self._handle_validation_failure(
                output,
                gen_input,
                validation_result,
                attempt_number,
            )

        content = validation_result.validated_content or ""
        return await self._persist_validated_output(
            output,
            gen_input,
            content,
            validation_result,
            llm_result.invocation_metadata,
            attempt_number,
        )

    def _is_retryable_error(self, error_code: str, current_attempt: int) -> bool:
        non_retryable_codes = {
            "STRUCTURAL_VIOLATION",
            "QUALITY_FAILURE",
            "VALIDATION_FAILURE",
            "CONTAINS_MARKUP",
            "CONTAINS_TAGS",
            "CONTAINS_HEADERS",
            "STRUCTURAL_MODIFICATION",
        }
        if error_code in non_retryable_codes:
            return False
        if current_attempt >= self.retry_policy.max_retries:
            return False
        return True

    async def _record_retry_attempt(
        self,
        output: SectionOutput,
        error_code: str,
        error_message: str,
        attempt_number: int,
    ) -> None:
        retry_entry = {
            "attempt": attempt_number,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": utc_now().isoformat(),
        }
        await self.output_repo.increment_retry_count(
            output_id=output.id,
            failure_category=FailureCategory.GENERATION_FAILURE.value,
            error_message=error_message,
            error_code=error_code,
            retry_entry=retry_entry,
        )

    def _assemble_prompt(self, gen_input: GenerationInput) -> str:
        prompt_config = gen_input.prompt_config
        hierarchy_context = gen_input.hierarchy_context
        client_data = gen_input.client_data
        surrounding_context = gen_input.surrounding_context

        prompt_parts = [
            f"Generate content for section at path: {gen_input.structural_path}",
            f"Classification confidence: {prompt_config.get('classification_confidence', 'N/A')}",
            f"Justification: {prompt_config.get('justification', 'N/A')}",
        ]

        if hierarchy_context.get("path_segments"):
            prompt_parts.append(
                f"Document structure: {' > '.join(hierarchy_context['path_segments'])}"
            )

        if client_data.get("client_name"):
            prompt_parts.append(f"Client: {client_data['client_name']}")

        if client_data.get("data_fields"):
            for key, value in client_data["data_fields"].items():
                prompt_parts.append(f"{key}: {value}")

        if surrounding_context.get("preceding_content"):
            prompt_parts.append(f"Preceding section: {surrounding_context['preceding_content']}")

        if surrounding_context.get("following_content"):
            prompt_parts.append(f"Following section: {surrounding_context['following_content']}")

        custom_template = prompt_config.get("prompt_template")
        if custom_template:
            prompt_parts.append(f"Template guidance: {custom_template}")

        return "\n".join(prompt_parts)

    async def _persist_validated_output(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        content: str,
        validation_result: Any,
        invocation_metadata: dict[str, Any],
        attempt_number: int,
    ) -> SectionGenerationResult:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        content_length = len(content)

        validation_data = {
            "is_valid": validation_result.is_valid,
            "error_codes": [c.value for c in validation_result.all_error_codes],
            "structural_valid": validation_result.structural_result.is_valid,
            "bounds_valid": validation_result.bounds_result.is_valid,
            "quality_valid": validation_result.quality_result.is_valid,
        }

        metadata = {
            "invocation": invocation_metadata,
            "input_hash": gen_input.input_hash,
            "structural_path": gen_input.structural_path,
            "attempt_number": attempt_number,
            "validation": validation_data,
        }

        await self.output_repo.mark_output_validated(
            output_id=output.id,
            generated_content=content,
            content_length=content_length,
            content_hash=content_hash,
            validation_result=validation_data,
            metadata=metadata,
            completed_at=utc_now(),
        )

        return SectionGenerationResult(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            status="VALIDATED",
            generated_content=content,
            content_length=content_length,
            content_hash=content_hash,
            metadata=metadata,
        )

    async def _handle_llm_failure(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        error_message: str | None,
        attempt_number: int = 0,
    ) -> SectionGenerationResult:
        error_msg = error_message or "LLM invocation failed"
        is_retryable = self._is_retryable_error("LLM_FAILURE", attempt_number)
        metadata = {
            "input_hash": gen_input.input_hash,
            "structural_path": gen_input.structural_path,
            "failure_type": FailureCategory.GENERATION_FAILURE.value,
            "attempt_number": attempt_number,
        }

        if not is_retryable:
            await self.output_repo.mark_retry_exhausted(
                output_id=output.id,
                error_message=f"Retry exhausted after {attempt_number + 1} attempts: {error_msg}",
                metadata=metadata,
                completed_at=utc_now(),
            )

        return SectionGenerationResult(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            status="RETRY" if is_retryable else "FAILED",
            error_message=error_msg,
            error_code="LLM_INVOCATION_FAILED",
            metadata=metadata,
        )

    async def _handle_validation_failure(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        validation_result: Any,
        attempt_number: int = 0,
    ) -> SectionGenerationResult:
        error_msg = validation_result.rejection_reason or "Content validation failed"
        failure_type = validation_result.failure_type or FailureType.VALIDATION_FAILURE
        error_codes = [c.value for c in validation_result.all_error_codes]

        error_code = failure_type.value
        if error_codes:
            error_code = error_codes[0]

        metadata = {
            "input_hash": gen_input.input_hash,
            "structural_path": gen_input.structural_path,
            "failure_type": failure_type.value,
            "violations": validation_result.all_violations,
            "error_codes": error_codes,
            "attempt_number": attempt_number,
            "is_retryable": validation_result.is_retryable,
        }

        is_retryable = validation_result.is_retryable and self._is_retryable_error(
            error_code,
            attempt_number,
        )

        if not is_retryable:
            await self.output_repo.mark_output_failed(
                output_id=output.id,
                error_message=error_msg,
                error_code=error_code,
                metadata=metadata,
                completed_at=utc_now(),
            )

        return SectionGenerationResult(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            status="RETRY" if is_retryable else "FAILED",
            error_message=error_msg,
            error_code=error_code,
            metadata=metadata,
        )

    async def _handle_retry_exhaustion(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        last_error: str,
        total_attempts: int,
    ) -> SectionGenerationResult:
        error_msg = f"Retry exhausted after {total_attempts} attempts: {last_error}"
        metadata = {
            "input_hash": gen_input.input_hash,
            "structural_path": gen_input.structural_path,
            "failure_type": FailureCategory.RETRY_EXHAUSTION.value,
            "total_attempts": total_attempts,
            "last_error": last_error,
        }

        await self.output_repo.mark_retry_exhausted(
            output_id=output.id,
            error_message=error_msg,
            metadata=metadata,
            completed_at=utc_now(),
        )

        return SectionGenerationResult(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            status="FAILED",
            error_message=error_msg,
            error_code="RETRY_EXHAUSTED",
            metadata=metadata,
        )

    async def _handle_missing_input(
        self,
        output: SectionOutput,
    ) -> SectionGenerationResult:
        error_msg = "Generation input not found"
        metadata = {"failure_type": "missing_input"}

        await self.output_repo.mark_output_failed(
            output_id=output.id,
            error_message=error_msg,
            error_code="MISSING_INPUT",
            metadata=metadata,
            completed_at=utc_now(),
        )

        return SectionGenerationResult(
            generation_input_id=output.generation_input_id,
            section_id=output.section_id,
            status="FAILED",
            error_message=error_msg,
            error_code="MISSING_INPUT",
            metadata=metadata,
        )

    async def _handle_unexpected_error(
        self,
        output: SectionOutput,
        gen_input: GenerationInput,
        error_str: str,
    ) -> SectionGenerationResult:
        metadata = {
            "input_hash": gen_input.input_hash,
            "structural_path": gen_input.structural_path,
            "failure_type": "unexpected",
        }

        await self.output_repo.mark_output_failed(
            output_id=output.id,
            error_message=error_str,
            error_code="UNEXPECTED_ERROR",
            metadata=metadata,
            completed_at=utc_now(),
        )

        return SectionGenerationResult(
            generation_input_id=gen_input.id,
            section_id=gen_input.section_id,
            status="FAILED",
            error_message=error_str,
            error_code="UNEXPECTED_ERROR",
            metadata=metadata,
        )

    def _build_response(self, batch: SectionOutputBatch) -> ExecuteSectionGenerationResponse:
        output_responses = [
            SectionOutputResponse(
                id=out.id,
                batch_id=out.batch_id,
                generation_input_id=out.generation_input_id,
                section_id=out.section_id,
                sequence_order=out.sequence_order,
                status=out.status.value,
                generated_content=out.generated_content,
                content_length=out.content_length,
                content_hash=out.content_hash,
                error_message=out.error_message,
                error_code=out.error_code,
                generation_metadata=out.generation_metadata,
                is_immutable=out.is_immutable,
                created_at=out.created_at,
                completed_at=out.completed_at,
            )
            for out in batch.outputs
        ]

        return ExecuteSectionGenerationResponse(
            batch_id=batch.id,
            input_batch_id=batch.input_batch_id,
            document_id=batch.document_id,
            version_intent=batch.version_intent,
            status=batch.status.value,
            total_sections=batch.total_sections,
            completed_sections=batch.completed_sections,
            failed_sections=batch.failed_sections,
            outputs=output_responses,
        )

    async def get_output_batch(self, batch_id: UUID) -> SectionOutputBatch | None:
        return await self.output_repo.get_batch_by_id(batch_id, include_outputs=True)

    async def get_output_by_section(self, batch_id: UUID, section_id: int) -> SectionOutput | None:
        outputs = await self.output_repo.get_outputs_by_batch(batch_id)
        for output in outputs:
            if output.section_id == section_id:
                return output
        return None

    async def get_validated_outputs(self, batch_id: UUID) -> list[SectionOutput]:
        outputs = await self.output_repo.get_validated_outputs(batch_id)
        return list(outputs)

    async def get_failed_outputs(self, batch_id: UUID) -> list[SectionOutput]:
        outputs = await self.output_repo.get_failed_outputs(batch_id)
        return list(outputs)

    async def get_outputs_by_failure_category(
        self,
        batch_id: UUID,
        failure_category: str,
    ) -> list[SectionOutput]:
        outputs = await self.output_repo.get_outputs_by_failure_category(
            batch_id,
            failure_category,
        )
        return list(outputs)

    async def get_retryable_outputs(self, batch_id: UUID) -> list[SectionOutput]:
        outputs = await self.output_repo.get_retryable_outputs(batch_id)
        return list(outputs)

    async def is_batch_ready_for_assembly(self, batch_id: UUID) -> bool:
        batch = await self.output_repo.get_batch_by_id(batch_id, include_outputs=True)
        if not batch:
            return False

        if not batch.is_immutable:
            return False

        for output in batch.outputs:
            if not output.is_ready_for_assembly:
                return False

        return True

    async def get_assembly_ready_outputs(self, batch_id: UUID) -> list[SectionOutput]:
        batch = await self.output_repo.get_batch_by_id(batch_id, include_outputs=True)
        if not batch:
            return []

        return [out for out in batch.outputs if out.is_ready_for_assembly]
