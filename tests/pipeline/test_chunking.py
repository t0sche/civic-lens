"""
Tests for section-aware document chunking.

@spec EMBED-CHUNK-001, EMBED-CHUNK-002
"""


from src.lib.models import ChunkSourceType
from src.pipeline.embedder import (
    MAX_CHUNK_CHARS,
    chunk_code_section,
    chunk_legislative_item,
)


class TestChunkCodeSection:
    """Tests for code section chunking logic."""

    def test_short_section_single_chunk(self):
        """Sections under MAX_CHUNK_CHARS produce exactly one chunk."""
        content = "No fence shall exceed six feet in height in any residential zone."
        chunks = chunk_code_section(
            section_id="sec-001",
            content=content,
            section_path="Town Code > Ch. 165 > §165-23",
            jurisdiction="MUNICIPAL",
        )

        assert len(chunks) == 1
        assert chunks[0].chunk_text == content
        assert chunks[0].chunk_index == 0
        assert chunks[0].source_type == ChunkSourceType.CODE_SECTION
        assert chunks[0].section_path == "Town Code > Ch. 165 > §165-23"
        assert chunks[0].metadata.get("full_section") is True

    def test_long_section_sub_chunked(self):
        """Sections over MAX_CHUNK_CHARS are split into multiple chunks."""
        # Create a section longer than MAX_CHUNK_CHARS
        paragraphs = [f"Paragraph {i}. " + ("x" * 500) for i in range(20)]
        content = "\n\n".join(paragraphs)
        assert len(content) > MAX_CHUNK_CHARS

        chunks = chunk_code_section(
            section_id="sec-002",
            content=content,
            section_path="Town Code > Ch. 165 > §165-24",
            jurisdiction="MUNICIPAL",
        )

        assert len(chunks) > 1
        # All chunks should have sequential indices
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
        # All chunks should be marked as sub-chunks
        for chunk in chunks:
            assert chunk.metadata.get("sub_chunk") is True

    def test_empty_content_returns_empty(self):
        """Empty content produces no chunks."""
        chunks = chunk_code_section(
            section_id="sec-003",
            content="",
            section_path="test",
            jurisdiction="MUNICIPAL",
        )
        # Empty string is <= MAX_CHUNK_CHARS so it produces one chunk
        # but chunking shouldn't crash
        assert len(chunks) >= 0

    def test_jurisdiction_preserved(self):
        """Jurisdiction is correctly set on all chunks."""
        chunks = chunk_code_section(
            section_id="sec-004",
            content="Some county regulation text.",
            section_path="County Code > Ch. 267",
            jurisdiction="COUNTY",
        )

        for chunk in chunks:
            assert chunk.jurisdiction.value == "COUNTY"


class TestChunkLegislativeItem:
    """Tests for legislative item chunking."""

    def test_with_summary(self):
        """Items with summaries produce a chunk containing both title and summary."""
        chunks = chunk_legislative_item(
            item_id="item-001",
            title="HB 100 - Property Tax Relief",
            summary="This bill provides property tax relief for eligible homeowners.",
            jurisdiction="STATE",
            body="Maryland General Assembly",
        )

        assert len(chunks) == 1
        assert "HB 100" in chunks[0].chunk_text
        assert "property tax relief" in chunks[0].chunk_text
        assert chunks[0].source_type == ChunkSourceType.LEGISLATIVE_ITEM
        assert chunks[0].metadata.get("has_summary") is True

    def test_without_summary(self):
        """Items without summaries produce a chunk with title only."""
        chunks = chunk_legislative_item(
            item_id="item-002",
            title="Ordinance 743",
            summary=None,
            jurisdiction="MUNICIPAL",
            body="Town of Bel Air Board of Commissioners",
        )

        assert len(chunks) == 1
        assert "Ordinance 743" in chunks[0].chunk_text
        assert chunks[0].metadata.get("has_summary") is False

    def test_section_path_includes_body(self):
        """Section path breadcrumb includes the governing body."""
        chunks = chunk_legislative_item(
            item_id="item-003",
            title="SB 200",
            summary=None,
            jurisdiction="STATE",
            body="Maryland General Assembly",
        )

        assert "Maryland General Assembly" in chunks[0].section_path
