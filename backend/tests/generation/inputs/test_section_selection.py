from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from backend.app.domains.generation.errors import NoDynamicSectionsError
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.section.models import Section, SectionType


class TestDynamicSectionSelection:
    @pytest.mark.asyncio
    async def test_only_dynamic_sections_selected(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mixed_sections: list[Section],
        fixed_template_version_id: UUID,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        dynamic_sections = await generation_service._get_dynamic_sections(fixed_template_version_id)
        assert len(dynamic_sections) == 3  # Only the 3 DYNAMIC sections
        for section in dynamic_sections:
            assert section.section_type == SectionType.DYNAMIC

    @pytest.mark.asyncio
    async def test_static_sections_never_included(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mixed_sections: list[Section],
        fixed_template_version_id: UUID,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        dynamic_sections = await generation_service._get_dynamic_sections(fixed_template_version_id)
        static_paths = {"header/logo", "body/legal_disclaimer", "footer/copyright"}
        selected_paths = {s.structural_path for s in dynamic_sections}
        assert static_paths.isdisjoint(selected_paths)

    @pytest.mark.asyncio
    async def test_all_dynamic_sections_included(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mixed_sections: list[Section],
        fixed_template_version_id: UUID,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        expected_dynamic_paths = {"body/greeting", "body/main_content", "body/closing"}
        dynamic_sections = await generation_service._get_dynamic_sections(fixed_template_version_id)
        selected_paths = {s.structural_path for s in dynamic_sections}
        assert selected_paths == expected_dynamic_paths

    @pytest.mark.asyncio
    async def test_no_dynamic_sections_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        fixed_template_version_id: UUID,
    ):
        static_only = [
            Section(
                id=1,
                template_version_id=fixed_template_version_id,
                section_type=SectionType.STATIC,
                structural_path="body/static_1",
                prompt_config=None,
            ),
            Section(
                id=2,
                template_version_id=fixed_template_version_id,
                section_type=SectionType.STATIC,
                structural_path="body/static_2",
                prompt_config=None,
            ),
        ]
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=static_only)
        with pytest.raises(NoDynamicSectionsError) as exc_info:
            await generation_service._get_dynamic_sections(fixed_template_version_id)

        assert exc_info.value.template_version_id == fixed_template_version_id
        assert "No DYNAMIC sections found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_sections_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        fixed_template_version_id: UUID,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=[])
        with pytest.raises(NoDynamicSectionsError):
            await generation_service._get_dynamic_sections(fixed_template_version_id)


class TestDeterministicOrdering:
    def test_ordering_by_id_primary(
        self,
        generation_service: GenerationInputService,
        fixed_template_version_id: UUID,
    ):
        sections = [
            self._create_section(3, "path_c", fixed_template_version_id),
            self._create_section(1, "path_a", fixed_template_version_id),
            self._create_section(2, "path_b", fixed_template_version_id),
        ]
        ordered = generation_service._order_sections_deterministically(sections)
        assert [s.id for s in ordered] == [1, 2, 3]

    def test_ordering_by_path_secondary(
        self,
        generation_service: GenerationInputService,
        fixed_template_version_id: UUID,
    ):
        sections = [
            self._create_section(1, "z_path", fixed_template_version_id),
            self._create_section(1, "a_path", fixed_template_version_id),
            self._create_section(1, "m_path", fixed_template_version_id),
        ]
        ordered = generation_service._order_sections_deterministically(sections)
        assert ordered[0].structural_path == "a_path"
        assert ordered[1].structural_path == "m_path"
        assert ordered[2].structural_path == "z_path"

    def test_ordering_is_stable_across_calls(
        self,
        generation_service: GenerationInputService,
        multiple_dynamic_sections: list[Section],
    ):
        results = []
        for _ in range(10):
            ordered = generation_service._order_sections_deterministically(
                multiple_dynamic_sections.copy()
            )
            results.append([s.id for s in ordered])
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result

    def test_ordering_independent_of_input_order(
        self,
        generation_service: GenerationInputService,
        multiple_dynamic_sections: list[Section],
    ):
        import random

        shuffled = multiple_dynamic_sections.copy()
        random.shuffle(shuffled)
        ordered_from_shuffled = generation_service._order_sections_deterministically(shuffled)

        ordered_from_original = generation_service._order_sections_deterministically(
            multiple_dynamic_sections
        )
        assert [s.id for s in ordered_from_shuffled] == [s.id for s in ordered_from_original]

    def test_ordering_preserves_all_sections(
        self,
        generation_service: GenerationInputService,
        multiple_dynamic_sections: list[Section],
    ):
        ordered = generation_service._order_sections_deterministically(multiple_dynamic_sections)
        assert len(ordered) == len(multiple_dynamic_sections)
        original_ids = {s.id for s in multiple_dynamic_sections}
        ordered_ids = {s.id for s in ordered}
        assert original_ids == ordered_ids

    def test_single_section_ordering(
        self,
        generation_service: GenerationInputService,
        sample_dynamic_section: Section,
    ):
        ordered = generation_service._order_sections_deterministically([sample_dynamic_section])
        assert len(ordered) == 1
        assert ordered[0].id == sample_dynamic_section.id

    def test_empty_list_ordering(
        self,
        generation_service: GenerationInputService,
    ):
        ordered = generation_service._order_sections_deterministically([])
        assert ordered == []

    @staticmethod
    def _create_section(section_id: int, path: str, template_version_id: UUID) -> Section:
        section = Section(
            id=section_id,
            template_version_id=template_version_id,
            section_type=SectionType.DYNAMIC,
            structural_path=path,
            prompt_config={
                "classification_confidence": 0.9,
                "classification_method": "RULE_BASED",
                "justification": "Test section",
                "metadata": {},
            },
        )
        section.created_at = datetime(2026, 1, 1, 12, 0, section_id)
        return section


class TestSelectionWithDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_selection_with_persisted_sections(
        self,
        db_session,
        db_section_repository,
        db_generation_service,
        fixed_template_version_id: UUID,
    ):
        pytest.skip("Requires template infrastructure setup")
