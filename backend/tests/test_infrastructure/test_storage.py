"""
Tests for Object Storage infrastructure.

Verifies:
- Template source upload/download
- Template parsed upload/download
- Document output upload
- File existence checking
- Path construction
"""

from io import BytesIO
from uuid import uuid4


class TestTemplateStorage:
    """Tests for template-related storage operations."""

    def test_upload_template_source(self, mock_storage):
        """Should upload a template source and return the path."""
        template_id = uuid4()
        version = 1
        content = b"Test DOCX content"
        file_obj = BytesIO(content)

        path = mock_storage.upload_template_source(template_id, version, file_obj)

        assert path == f"templates/{template_id}/{version}/source.docx"

    def test_get_template_source(self, mock_storage):
        """Should retrieve template source content."""
        template_id = uuid4()
        version = 1
        content = b"Test DOCX content"
        file_obj = BytesIO(content)

        mock_storage.upload_template_source(template_id, version, file_obj)

        retrieved = mock_storage.get_template_source(template_id, version)

        assert retrieved == content

    def test_get_template_source_not_found(self, mock_storage):
        """Should return None for non-existent template source."""
        template_id = uuid4()
        version = 999

        result = mock_storage.get_template_source(template_id, version)

        assert result is None

    def test_template_source_exists(self, mock_storage):
        """Should check if template source exists."""
        template_id = uuid4()
        version = 1
        content = b"Test DOCX content"
        file_obj = BytesIO(content)

        # Initially doesn't exist
        assert mock_storage.template_source_exists(template_id, version) is False

        # After upload, exists
        mock_storage.upload_template_source(template_id, version, file_obj)
        assert mock_storage.template_source_exists(template_id, version) is True

    def test_upload_template_parsed(self, mock_storage):
        """Should upload parsed template JSON and return the path."""
        template_id = uuid4()
        version = 1
        content = b'{"sections": []}'
        file_obj = BytesIO(content)

        path = mock_storage.upload_template_parsed(template_id, version, file_obj)

        assert path == f"templates/{template_id}/{version}/parsed.json"

    def test_upload_template_parsed_json(self, mock_storage):
        """Should upload parsed template from dict."""
        template_id = uuid4()
        version = 1
        parsed_data = {
            "sections": [{"id": "1", "type": "STATIC", "content": "Header"}],
            "metadata": {"total_sections": 1},
        }

        path = mock_storage.upload_template_parsed_json(template_id, version, parsed_data)

        assert path == f"templates/{template_id}/{version}/parsed.json"

        # Verify we can retrieve it
        retrieved = mock_storage.get_template_parsed(template_id, version)
        assert retrieved == parsed_data

    def test_get_template_parsed(self, mock_storage):
        """Should retrieve parsed template as dict."""
        template_id = uuid4()
        version = 1
        parsed_data = {"sections": [], "version": "1.0"}

        mock_storage.upload_template_parsed_json(template_id, version, parsed_data)

        retrieved = mock_storage.get_template_parsed(template_id, version)

        assert retrieved == parsed_data

    def test_get_template_parsed_not_found(self, mock_storage):
        """Should return None for non-existent parsed template."""
        template_id = uuid4()
        version = 999

        result = mock_storage.get_template_parsed(template_id, version)

        assert result is None

    def test_template_parsed_exists(self, mock_storage):
        """Should check if parsed template exists."""
        template_id = uuid4()
        version = 1

        # Initially doesn't exist
        assert mock_storage.template_parsed_exists(template_id, version) is False

        # After upload, exists
        mock_storage.upload_template_parsed_json(template_id, version, {"sections": []})
        assert mock_storage.template_parsed_exists(template_id, version) is True


class TestDocumentStorage:
    """Tests for document-related storage operations."""

    def test_upload_document_output(self, mock_storage):
        """Should upload document output and return the path."""
        document_id = uuid4()
        version = 1
        content = b"Generated DOCX content"
        file_obj = BytesIO(content)

        path = mock_storage.upload_document_output(document_id, version, file_obj)

        assert path == f"documents/{document_id}/{version}/output.docx"


class TestGenericStorageOperations:
    """Tests for generic file operations."""

    def test_get_file(self, mock_storage):
        """Should retrieve file by key."""
        template_id = uuid4()
        version = 1
        content = b"Test content"
        file_obj = BytesIO(content)

        mock_storage.upload_template_source(template_id, version, file_obj)
        key = f"templates/{template_id}/{version}/source.docx"

        retrieved = mock_storage.get_file(key)

        assert retrieved == content

    def test_get_file_not_found(self, mock_storage):
        """Should return None for non-existent key."""
        result = mock_storage.get_file("nonexistent/path/file.txt")

        assert result is None

    def test_file_exists(self, mock_storage):
        """Should check if file exists by key."""
        template_id = uuid4()
        version = 1
        content = b"Test content"
        file_obj = BytesIO(content)

        mock_storage.upload_template_source(template_id, version, file_obj)
        key = f"templates/{template_id}/{version}/source.docx"

        assert mock_storage.file_exists(key) is True
        assert mock_storage.file_exists("nonexistent/path") is False

    def test_delete_file(self, mock_storage):
        """Should delete a file by key."""
        template_id = uuid4()
        version = 1
        content = b"Test content"
        file_obj = BytesIO(content)

        mock_storage.upload_template_source(template_id, version, file_obj)
        key = f"templates/{template_id}/{version}/source.docx"

        # Verify it exists
        assert mock_storage.file_exists(key) is True

        # Delete it
        result = mock_storage.delete_file(key)

        assert result is True
        assert mock_storage.file_exists(key) is False

    def test_delete_file_not_found(self, mock_storage):
        """Should return False when deleting non-existent file."""
        result = mock_storage.delete_file("nonexistent/path/file.txt")

        assert result is False


class TestStoragePathPatterns:
    """Tests for storage path patterns and conventions."""

    def test_template_source_path_pattern(self, mock_storage):
        """Template source paths should follow pattern: templates/{id}/{version}/source.docx"""
        template_id = uuid4()
        version = 1

        path = mock_storage.upload_template_source(template_id, version, BytesIO(b"content"))

        parts = path.split("/")
        assert parts[0] == "templates"
        assert parts[1] == str(template_id)
        assert parts[2] == str(version)
        assert parts[3] == "source.docx"

    def test_template_parsed_path_pattern(self, mock_storage):
        """Template parsed paths should follow pattern: templates/{id}/{version}/parsed.json"""
        template_id = uuid4()
        version = 1

        path = mock_storage.upload_template_parsed_json(template_id, version, {"sections": []})

        parts = path.split("/")
        assert parts[0] == "templates"
        assert parts[1] == str(template_id)
        assert parts[2] == str(version)
        assert parts[3] == "parsed.json"

    def test_document_output_path_pattern(self, mock_storage):
        """Document output paths should follow pattern: documents/{id}/{version}/output.docx"""
        document_id = uuid4()
        version = 1

        path = mock_storage.upload_document_output(document_id, version, BytesIO(b"content"))

        parts = path.split("/")
        assert parts[0] == "documents"
        assert parts[1] == str(document_id)
        assert parts[2] == str(version)
        assert parts[3] == "output.docx"


class TestStorageVersioning:
    """Tests for storage versioning behavior."""

    def test_multiple_versions_stored_separately(self, mock_storage):
        """Different versions should be stored at different paths."""
        template_id = uuid4()

        # Upload version 1
        mock_storage.upload_template_source(template_id, 1, BytesIO(b"Version 1 content"))

        # Upload version 2
        mock_storage.upload_template_source(template_id, 2, BytesIO(b"Version 2 content"))

        # Both versions should exist and have different content
        v1 = mock_storage.get_template_source(template_id, 1)
        v2 = mock_storage.get_template_source(template_id, 2)

        assert v1 == b"Version 1 content"
        assert v2 == b"Version 2 content"

    def test_overwrite_same_version(self, mock_storage):
        """Uploading to same version should overwrite."""
        template_id = uuid4()
        version = 1

        # Upload initial content
        mock_storage.upload_template_source(template_id, version, BytesIO(b"Initial content"))

        # Upload new content to same version
        mock_storage.upload_template_source(template_id, version, BytesIO(b"Updated content"))

        # Should have the updated content
        content = mock_storage.get_template_source(template_id, version)
        assert content == b"Updated content"


class TestStorageFileFormats:
    """Tests for handling different file formats."""

    def test_upload_binary_content(self, mock_storage):
        """Should handle binary content correctly."""
        template_id = uuid4()
        version = 1

        # Binary content with various byte values
        binary_content = bytes(range(256))
        file_obj = BytesIO(binary_content)

        mock_storage.upload_template_source(template_id, version, file_obj)

        retrieved = mock_storage.get_template_source(template_id, version)
        assert retrieved == binary_content

    def test_upload_json_preserves_structure(self, mock_storage):
        """Should preserve JSON structure when uploading parsed data."""
        template_id = uuid4()
        version = 1

        complex_data = {
            "sections": [
                {
                    "id": "section-1",
                    "type": "STATIC",
                    "content": "Introduction",
                    "children": [{"id": "child-1", "content": "Subsection"}],
                }
            ],
            "metadata": {"total_sections": 2, "nested_levels": 2, "has_tables": False},
        }

        mock_storage.upload_template_parsed_json(template_id, version, complex_data)

        retrieved = mock_storage.get_template_parsed(template_id, version)
        assert retrieved == complex_data


class TestStorageIsolation:
    """Tests for storage isolation between entities."""

    def test_templates_isolated_by_id(self, mock_storage):
        """Templates with different IDs should be isolated."""
        template_id_1 = uuid4()
        template_id_2 = uuid4()
        version = 1

        mock_storage.upload_template_source(template_id_1, version, BytesIO(b"Template 1"))
        mock_storage.upload_template_source(template_id_2, version, BytesIO(b"Template 2"))

        content_1 = mock_storage.get_template_source(template_id_1, version)
        content_2 = mock_storage.get_template_source(template_id_2, version)

        assert content_1 == b"Template 1"
        assert content_2 == b"Template 2"

    def test_source_and_parsed_isolated(self, mock_storage):
        """Source and parsed files should be stored separately."""
        template_id = uuid4()
        version = 1

        mock_storage.upload_template_source(template_id, version, BytesIO(b"Source content"))
        mock_storage.upload_template_parsed_json(template_id, version, {"type": "parsed"})

        source = mock_storage.get_template_source(template_id, version)
        parsed = mock_storage.get_template_parsed(template_id, version)

        assert source == b"Source content"
        assert parsed == {"type": "parsed"}
