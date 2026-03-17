"""
Tests for embedding model validation.

Verifies that only the Gemini embedding model (768-dim, matching the
pgvector schema) is accepted, and that incompatible models are rejected.

@spec DATA-EMBED-003
"""

from unittest.mock import patch, MagicMock

import pytest

from src.pipeline.embedder import generate_embeddings, EMBEDDING_DIM


class TestEmbeddingModelValidation:
    """Ensure the embedding pipeline rejects incompatible models."""

    def test_rejects_minilm(self, monkeypatch):
        """MiniLM (384-dim) is rejected since DB schema requires 768-dim."""
        monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("EMBEDDING_MODEL", "minilm")

        with pytest.raises(ValueError, match="Unsupported embedding model"):
            generate_embeddings(["test text"])

    def test_rejects_unknown_model(self, monkeypatch):
        """Unknown model names are rejected."""
        monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("EMBEDDING_MODEL", "openai-ada")

        with pytest.raises(ValueError, match="Unsupported embedding model"):
            generate_embeddings(["test text"])

    def test_embedding_dim_constant(self):
        """EMBEDDING_DIM matches the pgvector schema (768)."""
        assert EMBEDDING_DIM == 768
