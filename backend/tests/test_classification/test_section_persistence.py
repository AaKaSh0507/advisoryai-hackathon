import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import ClassificationMethod
from backend.app.domains.section.classification_service import create_classification_service
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.section.schemas import SectionCreate


class TestSectionModelStructure:
    def test_section_model_exists(self):
        assert Section is not None

    def test_section_type_enum_values(self):
        assert hasattr(SectionType, "STATIC")
        assert hasattr(SectionType, "DYNAMIC")
        assert SectionType.STATIC.value == "STATIC"
        assert SectionType.DYNAMIC.value == "DYNAMIC"

    def test_section_has_required_fields(self):
        columns = [c.name for c in Section.__table__.columns]
        assert "id" in columns
        assert "template_version_id" in columns
        assert "section_type" in columns

    def test_section_has_prompt_config_field(self):
        columns = [c.name for c in Section.__table__.columns]
        assert "prompt_config" in columns


class TestSectionSchemaStructure:
    def test_section_create_schema_exists(self):
        assert SectionCreate is not None

    def test_section_create_has_required_fields(self):
        fields = SectionCreate.model_fields
        assert "template_version_id" in fields
        assert "section_type" in fields

    def test_section_create_validates_section_type(self):
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.STATIC,
            structural_path="body/paragraph[0]",
        )
        assert section.section_type == SectionType.STATIC
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.DYNAMIC,
            structural_path="body/paragraph[1]",
        )
        assert section.section_type == SectionType.DYNAMIC


class TestSectionRepository:
    def test_section_repository_exists(self):
        assert SectionRepository is not None

    def test_repository_has_create_batch_method(self):
        assert hasattr(SectionRepository, "create_batch")

    def test_repository_has_get_by_template_version_method(self):
        assert hasattr(SectionRepository, "get_by_template_version_id")


class TestPromptConfigStorage:
    @pytest.fixture
    def section_data(self):
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
        config = section_data["prompt_config"]
        serialized = json.dumps(config)
        assert serialized is not None
        deserialized = json.loads(serialized)
        assert deserialized == config

    def test_prompt_config_structure(self, section_data):
        section = SectionCreate(**section_data)
        assert section.prompt_config is not None
        assert "placeholder" in section.prompt_config
        assert section.prompt_config["placeholder"] == "{client_name}"


class TestSectionImmutability:
    def test_section_type_cannot_be_empty(self):
        with pytest.raises((ValueError, TypeError)):
            SectionCreate(
                template_version_id=uuid4(),
                section_type="",
                structural_path="body/paragraph[0]",
            )

    def test_structural_path_required(self):
        section = SectionCreate(
            template_version_id=uuid4(),
            section_type=SectionType.STATIC,
            structural_path="body/paragraph[0]",
        )
        assert section.structural_path == "body/paragraph[0]"


class TestNoDuplicateSections:
    @pytest.fixture
    def mock_section_repo(self):
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
        service = create_classification_service(confidence_threshold=0.85)
        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )
        mock_section_repo.create_batch.assert_called()
        assert result.total_sections == len(sample_document.blocks)

    @pytest.mark.asyncio
    async def test_idempotent_classification(self, sample_document):
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )
        mock_repo1 = MagicMock()
        mock_repo1.created_sections = []
        mock_repo1.create_batch = AsyncMock(
            side_effect=lambda sections: mock_repo1.created_sections.extend(sections) or sections
        )
        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo1,
        )
        mock_repo2 = MagicMock()
        mock_repo2.created_sections = []
        mock_repo2.create_batch = AsyncMock(
            side_effect=lambda sections: mock_repo2.created_sections.extend(sections) or sections
        )
        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert c1.section_type == c2.section_type
            assert c1.confidence_score == c2.confidence_score


class TestClassificationToPersistenceMapping:
    @pytest.fixture
    def mock_section_repo(self):
        mock_repo = MagicMock()
        mock_repo.captured_sections = []

        async def capture_batch(sections):
            mock_repo.captured_sections = sections
            return sections

        mock_repo.create_batch = AsyncMock(side_effect=capture_batch)
        return mock_repo

    @pytest.mark.asyncio
    async def test_classification_result_structure(self, mock_section_repo):
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
        assert result.total_sections == 1
        classification = result.classifications[0]
        assert hasattr(classification, "section_type")
        assert classification.section_type in ["STATIC", "DYNAMIC"]

    @pytest.mark.asyncio
    async def test_classification_includes_confidence(self, mock_section_repo):
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
