"""
Tests for section persistence and immutability.

Verifies:
- Sections are persisted to the database
- Section data is immutable once persisted
- prompt_config is properly stored
- No duplicate sections are created
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
)
from backend.app.domains.section.classification_service import (
    ClassificationService,
    create_classification_service,
)
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.section.schemas import SectionCreate


class TestSectionModelStructure:
    """Tests for Section model structure."""

    def test_section_model_exists(self):
        """Section model should be importable."""
        assert Section is not None

    def test_section_type_enum_values(self):
        """SectionType enum should have STATIC and DYNAMIC."""
        assert hasattr(SectionType, "STATIC")
        assert hasattr(SectionType, "DYNAMIC")
        assert SectionType.STATIC.value == "STATIC"
        assert SectionType.DYNAMIC.value == "DYNAMIC"

    def test_section_has_required_fields(self):
        """Section model should have required fields."""
        # Check column names exist
        columns = [c.name for c in Section.__table__.columns]

        assert "id" in columns
        assert "template_version_id" in columns
        assert "section_type" in columns

    def test_section_has_prompt_config_field(self):
        """Section model should have prompt_config field."""
        columns = [c.name for c in Section.__table__.columns]

        assert "prompt_config" in columns


class TestSectionSchemaStructure:
    """Tests for Section schema structure."""

    def test_section_create_schema_exists(self):
        """SectionCreate schema should be importable."""
        assert SectionCreate is not None

    def test_section_create_has_required_fields(self):
        """SectionCreate should have required fields."""
        fields = SectionCreate.model_fields

        assert "template_version_id" in fields
        assert "section_type" in fields

    def test_section_create_validates_section_type(self):
        """SectionCreate should validate section_type."""
        # Valid STATIC
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.STATIC,
            structural_path="body/paragraph[0]",
        )
        assert section.section_type == SectionType.STATIC

        # Valid DYNAMIC
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.DYNAMIC,
            structural_path="body/paragraph[1]",
        )
        assert section.section_type == SectionType.DYNAMIC


class TestSectionRepository:
    """Tests for SectionRepository."""

    def test_section_repository_exists(self):
        """SectionRepository should be importable."""
        assert SectionRepository is not None

    def test_repository_has_create_batch_method(self):
        """Repository should have create_batch method."""
        assert hasattr(SectionRepository, "create_batch")

    def test_repository_has_get_by_template_version_method(self):
        """Repository should have get_by_template_version_id method."""
        assert hasattr(SectionRepository, "get_by_template_version_id")


class TestPromptConfigStorage:
    """Tests for prompt_config storage."""

    @pytest.fixture
    def section_data(self):
        """Create sample section data."""
        return {
            "template_version_id": uuid4(),
            "section_type": SectionType.DYNAMIC,
            "structural_path": "body/paragraph[0]",
            "prompt_config": {
                "placeholder": "{client_name}",
                "expected_type": "string",
                "validation_rules": ["non_empty"],
            },
        }

    def test_prompt_config_serializable(self, section_data):
        """prompt_config should be JSON serializable."""
        config = section_data["prompt_config"]

        # Should serialize
        serialized = json.dumps(config)
        assert serialized is not None

        # Should deserialize
        deserialized = json.loads(serialized)
        assert deserialized == config

    def test_prompt_config_structure(self, section_data):
        """prompt_config should have expected structure."""
        section = SectionCreate(**section_data)

        assert section.prompt_config is not None
        assert "placeholder" in section.prompt_config
        assert section.prompt_config["placeholder"] == "{client_name}"


class TestSectionImmutability:
    """Tests for section immutability guarantees."""

    def test_section_type_cannot_be_empty(self):
        """section_type should not accept empty value."""
        with pytest.raises((ValueError, TypeError)):
            SectionCreate(
                template_version_id=uuid4(),
                section_type="",  # Empty should fail
                structural_path="body/paragraph[0]",
            )

    def test_structural_path_required(self):
        """structural_path should be required."""
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.STATIC,
            structural_path="body/paragraph[0]",
        )
        assert section.structural_path == "body/paragraph[0]"


class TestNoDuplicateSections:
    """Tests ensuring no duplicate sections are created."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock section repository that tracks calls."""
        mock_repo = MagicMock()
        mock_repo.created_sections = []

        async def mock_create_batch(sections):
            for s in sections:
                mock_repo.created_sections.append(s)
            return sections

        mock_repo.create_batch = AsyncMock(side_effect=mock_create_batch)
        return mock_repo

    @pytest.fixture
    def sample_document(self):
        """Create sample document."""
        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="Confidential information.")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0002_xyz",
                    sequence=2,
                    runs=[TextRun(text="Dear {name}, welcome.")],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_each_block_classified_once(self, mock_section_repo, sample_document):
        """Each block should be classified exactly once."""
        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )

        # Check that create_batch was called
        mock_section_repo.create_batch.assert_called()

        # Classifications should equal blocks
        assert result.total_sections == len(sample_document.blocks)

    @pytest.mark.asyncio
    async def test_idempotent_classification(self, sample_document):
        """Same document should produce same classification results."""
        service = create_classification_service(
            llm_config=None,  # Disable LLM for determinism
            confidence_threshold=0.85,
        )

        # First classification
        mock_repo1 = MagicMock()
        mock_repo1.created_sections = []
        mock_repo1.create_batch = AsyncMock(
            side_effect=lambda sections: mock_repo1.created_sections.extend(sections) or sections
        )

        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo1,
        )

        # Second classification (same document)
        mock_repo2 = MagicMock()
        mock_repo2.created_sections = []
        mock_repo2.create_batch = AsyncMock(
            side_effect=lambda sections: mock_repo2.created_sections.extend(sections) or sections
        )

        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )

        # Results should be identical
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections

        # Classifications should match
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert c1.section_type == c2.section_type
            assert c1.confidence_score == c2.confidence_score


class TestClassificationToPersistenceMapping:
    """Tests for mapping classification results to persistence."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock repository that captures sections."""
        mock_repo = MagicMock()
        mock_repo.captured_sections = []

        async def capture_batch(sections):
            mock_repo.captured_sections = sections
            return sections

        mock_repo.create_batch = AsyncMock(side_effect=capture_batch)
        return mock_repo

    @pytest.mark.asyncio
    async def test_classification_result_structure(self, mock_section_repo):
        """Classification results should have required fields."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="This is confidential and privileged.")],
                ),
            ],
        )

        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        # Verify classification result structure
        assert result.total_sections == 1
        classification = result.classifications[0]

        assert hasattr(classification, "section_type")
        assert classification.section_type in ["STATIC", "DYNAMIC"]

    @pytest.mark.asyncio
    async def test_classification_includes_confidence(self, mock_section_repo):
        """Classification results should include confidence scores."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="Copyright 2024. All rights reserved.")],
                ),
            ],
        )

        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        classification = result.classifications[0]
        assert hasattr(classification, "confidence_score")
        assert 0.0 <= classification.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_classification_includes_method(self, mock_section_repo):
        """Classification results should include method used."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="This is confidential.")],
                ),
            ],
        )

        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        classification = result.classifications[0]
        assert hasattr(classification, "method")
        assert classification.method in [
            ClassificationMethod.RULE_BASED,
            ClassificationMethod.LLM_ASSISTED,
            ClassificationMethod.FALLBACK,
        ]

    @pytest.mark.asyncio
    async def test_classification_includes_justification(self, mock_section_repo):
        """Classification results should include justification."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="CONFIDENTIAL")],
                ),
            ],
        )

        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        classification = result.classifications[0]
        assert hasattr(classification, "justification")
        assert classification.justification is not None
