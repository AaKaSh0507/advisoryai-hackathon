import hashlib
import json
from uuid import UUID

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.generation.errors import (
    InputValidationError,
    MalformedSectionMetadataError,
    MissingPromptConfigError,
    NoDynamicSectionsError,
)
from backend.app.domains.generation.models import (
    GenerationInput,
    GenerationInputBatch,
    GenerationInputStatus,
)
from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.schemas import (
    ClientDataPayload,
    GenerationInputData,
    GenerationInputResponse,
    PrepareGenerationInputsRequest,
    PrepareGenerationInputsResponse,
    PromptConfigMetadata,
    SectionHierarchyContext,
    SurroundingContext,
)
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.infrastructure.datetime_utils import utc_now
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.generation.service")


class GenerationInputService:
    def __init__(
        self,
        generation_repo: GenerationInputRepository,
        section_repo: SectionRepository,
        generation_audit_service: GenerationAuditService | None = None,
    ):
        self.generation_repo = generation_repo
        self.section_repo = section_repo
        self.generation_audit_service = generation_audit_service

    async def prepare_generation_inputs(
        self,
        request: PrepareGenerationInputsRequest,
    ) -> PrepareGenerationInputsResponse:
        logger.info(
            f"Preparing generation inputs for document {request.document_id}, "
            f"template version {request.template_version_id}, "
            f"version intent {request.version_intent}"
        )

        dynamic_sections = await self._get_dynamic_sections(request.template_version_id)
        ordered_sections = self._order_sections_deterministically(dynamic_sections)
        logger.info(f"Found {len(ordered_sections)} DYNAMIC sections to process")
        all_sections = await self.section_repo.get_by_template_version_id(
            request.template_version_id
        )
        context_map = self._build_surrounding_context_map(ordered_sections, list(all_sections))
        generation_inputs_data: list[GenerationInputData] = []
        for sequence, section in enumerate(ordered_sections):
            input_data = self._assemble_input_for_section(
                section=section,
                sequence_order=sequence,
                client_data=request.client_data,
                surrounding_context=context_map.get(section.id),
                all_sections=list(all_sections),
            )
            self._validate_input(input_data)
            generation_inputs_data.append(input_data)
        batch_hash = self._compute_batch_hash(generation_inputs_data)
        batch = GenerationInputBatch(
            document_id=request.document_id,
            template_version_id=request.template_version_id,
            version_intent=request.version_intent,
            status=GenerationInputStatus.PENDING,
            content_hash=batch_hash,
            total_inputs=len(generation_inputs_data),
            is_immutable=False,
        )
        batch = await self.generation_repo.create_batch(batch)
        db_inputs: list[GenerationInput] = []
        for input_data in generation_inputs_data:
            db_input = GenerationInput(
                batch_id=batch.id,
                section_id=input_data.section_id,
                sequence_order=generation_inputs_data.index(input_data),
                template_id=UUID(input_data.template_id),
                template_version_id=UUID(input_data.template_version_id),
                structural_path=input_data.structural_path,
                hierarchy_context=input_data.hierarchy_context.model_dump(mode="json"),
                prompt_config=input_data.prompt_config.model_dump(mode="json"),
                client_data=input_data.client_data.model_dump(mode="json"),
                surrounding_context=input_data.surrounding_context.model_dump(mode="json"),
                input_hash=input_data.compute_hash(),
            )
            db_inputs.append(db_input)

        await self.generation_repo.create_inputs(db_inputs)
        validated_at = utc_now()
        await self.generation_repo.mark_batch_validated(batch.id, validated_at)
        refreshed_batch = await self.generation_repo.get_batch_by_id(batch.id, include_inputs=True)
        if refreshed_batch is None:
            raise RuntimeError(f"Failed to retrieve batch {batch.id} after validation")
        batch = refreshed_batch
        logger.info(
            f"Successfully prepared {len(db_inputs)} generation inputs for batch {batch.id}"
        )

        input_responses = [
            GenerationInputResponse(
                id=inp.id,
                batch_id=inp.batch_id,
                section_id=inp.section_id,
                sequence_order=inp.sequence_order,
                template_id=inp.template_id,
                template_version_id=inp.template_version_id,
                structural_path=inp.structural_path,
                hierarchy_context=inp.hierarchy_context,
                prompt_config=inp.prompt_config,
                client_data=inp.client_data,
                surrounding_context=inp.surrounding_context,
                input_hash=inp.input_hash,
                created_at=inp.created_at,
            )
            for inp in batch.inputs
        ]

        if self.generation_audit_service:
            await self.generation_audit_service.log_generation_initiated(
                batch_id=batch.id,
                document_id=batch.document_id,
                template_version_id=batch.template_version_id,
                version_intent=batch.version_intent,
                total_sections=len(input_responses),
            )

        return PrepareGenerationInputsResponse(
            batch_id=batch.id,
            document_id=batch.document_id,
            template_version_id=batch.template_version_id,
            version_intent=batch.version_intent,
            status=batch.status.value,
            total_dynamic_sections=len(input_responses),
            content_hash=batch.content_hash,
            is_immutable=batch.is_immutable,
            inputs=input_responses,
        )

    async def _get_dynamic_sections(self, template_version_id: UUID) -> list[Section]:
        sections = await self.section_repo.get_by_template_version_id(template_version_id)
        dynamic_sections = [s for s in sections if s.section_type == SectionType.DYNAMIC]

        if not dynamic_sections:
            raise NoDynamicSectionsError(template_version_id)

        return dynamic_sections

    def _order_sections_deterministically(self, sections: list[Section]) -> list[Section]:
        return sorted(sections, key=lambda s: (s.id, s.structural_path))

    def _build_surrounding_context_map(
        self,
        dynamic_sections: list[Section],
        all_sections: list[Section],
    ) -> dict[int, SurroundingContext]:
        sorted_sections = sorted(all_sections, key=lambda s: s.id)
        section_index_map = {s.id: i for i, s in enumerate(sorted_sections)}
        context_map: dict[int, SurroundingContext] = {}

        for section in dynamic_sections:
            idx = section_index_map.get(section.id)
            if idx is None:
                context_map[section.id] = SurroundingContext()
                continue

            preceding_content = None
            preceding_type = None
            following_content = None
            following_type = None

            if idx > 0:
                prev_section = sorted_sections[idx - 1]
                preceding_type = prev_section.section_type.value
                preceding_content = prev_section.structural_path

            if idx < len(sorted_sections) - 1:
                next_section = sorted_sections[idx + 1]
                following_type = next_section.section_type.value
                following_content = next_section.structural_path

            context_map[section.id] = SurroundingContext(
                preceding_content=preceding_content,
                preceding_type=preceding_type,
                following_content=following_content,
                following_type=following_type,
                section_boundary_hint=f"Section at position {idx + 1} of {len(sorted_sections)}",
            )

        return context_map

    def _assemble_input_for_section(
        self,
        section: Section,
        sequence_order: int,
        client_data: ClientDataPayload,
        surrounding_context: SurroundingContext | None,
        all_sections: list[Section],
    ) -> GenerationInputData:
        if not section.prompt_config:
            raise MissingPromptConfigError(
                section_id=section.id,
                structural_path=section.structural_path,
            )

        try:
            prompt_config = self._extract_prompt_config(section)
        except (KeyError, ValueError, TypeError) as e:
            raise MalformedSectionMetadataError(
                section_id=section.id,
                structural_path=section.structural_path,
                reason=str(e),
                invalid_data=section.prompt_config,
            )

        hierarchy_context = self._build_hierarchy_context(section, all_sections)

        return GenerationInputData(
            section_id=section.id,
            template_id=str(
                section.template_version_id
            ),  # Note: We use template_version_id from section
            template_version_id=str(section.template_version_id),
            structural_path=section.structural_path,
            hierarchy_context=hierarchy_context,
            prompt_config=prompt_config,
            client_data=client_data,
            surrounding_context=surrounding_context or SurroundingContext(),
        )

    def _extract_prompt_config(self, section: Section) -> PromptConfigMetadata:
        config = section.prompt_config
        if not isinstance(config, dict):
            raise TypeError(f"prompt_config must be a dict, got {type(config)}")

        required_fields = ["classification_confidence", "classification_method", "justification"]
        missing = [f for f in required_fields if f not in config]
        if missing:
            raise MissingPromptConfigError(
                section_id=section.id,
                structural_path=section.structural_path,
                missing_fields=missing,
            )

        return PromptConfigMetadata(
            classification_confidence=float(config["classification_confidence"]),
            classification_method=str(config["classification_method"]),
            justification=str(config["justification"]),
            prompt_template=config.get("prompt_template"),
            generation_hints=config.get("generation_hints", {}),
            metadata=config.get("metadata", {}),
        )

    def _build_hierarchy_context(
        self,
        section: Section,
        all_sections: list[Section],
    ) -> SectionHierarchyContext:
        path = section.structural_path
        path_segments = path.split("/") if "/" in path else [path]
        parent_path = "/".join(path_segments[:-1]) if len(path_segments) > 1 else ""
        siblings = [
            s
            for s in all_sections
            if s.structural_path.rsplit("/", 1)[0] == parent_path
            if "/" in s.structural_path or parent_path == ""
        ]
        sibling_ids = sorted(s.id for s in siblings)
        sibling_index = sibling_ids.index(section.id) if section.id in sibling_ids else 0

        return SectionHierarchyContext(
            parent_heading=path_segments[-2] if len(path_segments) > 1 else None,
            parent_level=len(path_segments) - 1 if len(path_segments) > 1 else None,
            sibling_index=sibling_index,
            total_siblings=len(siblings) if siblings else 1,
            depth=len(path_segments) - 1,
            path_segments=path_segments,
        )

    def _validate_input(self, input_data: GenerationInputData) -> None:
        if input_data.section_id <= 0:
            raise InputValidationError(
                field="section_id",
                reason="must be a positive integer",
                section_id=input_data.section_id,
                invalid_value=input_data.section_id,
            )
        try:
            UUID(input_data.template_id)
        except ValueError:
            raise InputValidationError(
                field="template_id",
                reason="must be a valid UUID string",
                section_id=input_data.section_id,
                invalid_value=input_data.template_id,
            )

        try:
            UUID(input_data.template_version_id)
        except ValueError:
            raise InputValidationError(
                field="template_version_id",
                reason="must be a valid UUID string",
                section_id=input_data.section_id,
                invalid_value=input_data.template_version_id,
            )

        if not input_data.structural_path or not input_data.structural_path.strip():
            raise InputValidationError(
                field="structural_path",
                reason="cannot be empty",
                section_id=input_data.section_id,
                invalid_value=input_data.structural_path,
            )

        if not 0.0 <= input_data.prompt_config.classification_confidence <= 1.0:
            raise InputValidationError(
                field="prompt_config.classification_confidence",
                reason="must be between 0.0 and 1.0",
                section_id=input_data.section_id,
                invalid_value=input_data.prompt_config.classification_confidence,
            )

    def _compute_batch_hash(self, inputs: list[GenerationInputData]) -> str:
        input_hashes = sorted(inp.compute_hash() for inp in inputs)
        combined = json.dumps(input_hashes, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    async def get_batch(self, batch_id: UUID) -> GenerationInputBatch | None:
        return await self.generation_repo.get_batch_by_id(batch_id, include_inputs=True)

    async def get_validated_batch_for_document(
        self,
        document_id: UUID,
        version_intent: int,
    ) -> GenerationInputBatch | None:
        return await self.generation_repo.get_validated_batch(document_id, version_intent)

    async def batch_exists(
        self,
        document_id: UUID,
        version_intent: int,
    ) -> bool:
        return await self.generation_repo.batch_exists(document_id, version_intent)
