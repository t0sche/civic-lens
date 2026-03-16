"""
Tests for Bronze layer content-hash deduplication.

Verifies that upsert_bronze_document skips writes for unchanged content
and correctly reports new/updated/skipped status.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.lib.supabase import upsert_bronze_document, content_hash


def _mock_supabase(existing_rows=None):
    """Create a mock Supabase client."""
    client = MagicMock()

    # Mock the select query for existing record check
    select_chain = MagicMock()
    select_chain.eq.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=existing_rows or [])
    client.table.return_value.select.return_value = select_chain

    # Mock the upsert
    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[{"id": "1", "source": "test"}])
    client.table.return_value.upsert.return_value = upsert_chain

    return client


class TestBronzeDedup:
    """Tests for content-hash dedup in upsert_bronze_document."""

    def test_new_document_returns_new_status(self):
        """First insert for a (source, source_id) reports status='new'."""
        client = _mock_supabase(existing_rows=[])

        result = upsert_bronze_document(
            client,
            source="openstates",
            source_id="bill-001",
            document_type="bill",
            raw_content='{"title": "Test Bill"}',
        )

        assert result["status"] == "new"
        # Upsert should have been called
        client.table.return_value.upsert.assert_called_once()

    def test_unchanged_document_returns_skipped(self):
        """Re-ingesting identical content skips the write."""
        raw = '{"title": "Test Bill"}'
        existing_hash = content_hash(raw)

        client = _mock_supabase(
            existing_rows=[{"content_hash": existing_hash}]
        )

        result = upsert_bronze_document(
            client,
            source="openstates",
            source_id="bill-001",
            document_type="bill",
            raw_content=raw,
        )

        assert result["status"] == "skipped"
        # Upsert should NOT have been called
        client.table.return_value.upsert.assert_not_called()

    def test_changed_document_returns_updated(self):
        """Re-ingesting with changed content performs the write."""
        client = _mock_supabase(
            existing_rows=[{"content_hash": "old-hash-value"}]
        )

        result = upsert_bronze_document(
            client,
            source="openstates",
            source_id="bill-001",
            document_type="bill",
            raw_content='{"title": "Updated Bill"}',
        )

        assert result["status"] == "updated"
        client.table.return_value.upsert.assert_called_once()

    def test_content_hash_is_deterministic(self):
        """Same content always produces the same hash."""
        text = "Some legal text about zoning."
        assert content_hash(text) == content_hash(text)

    def test_content_hash_changes_with_content(self):
        """Different content produces different hashes."""
        assert content_hash("version 1") != content_hash("version 2")
