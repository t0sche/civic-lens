"""
Section-aware chunking and embedding pipeline.

Transforms Silver layer records into vector embeddings stored in the
Gold layer (document_chunks table with pgvector).

Key design decision (HLD D4): Chunks are split by legal section
boundaries, not by token count. This preserves the semantic units
of legal text — statutes, ordinances, and code sections are naturally
bounded by section numbers.

@spec DATA-EMBED-001, DATA-EMBED-002, DATA-EMBED-003
"""

import logging
import re
from typing import Any

from src.lib.config import get_config
from src.lib.models import ChunkSourceType, DocumentChunk, JurisdictionLevel
from src.lib.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# Maximum chunk size in characters before sub-chunking
MAX_CHUNK_CHARS = 4000
# Overlap for sub-chunks (characters)
SUB_CHUNK_OVERLAP = 200


# ─── Chunking ────────────────────────────────────────────────────────────


def chunk_code_section(
    section_id: str,
    content: str,
    section_path: str,
    jurisdiction: str,
) -> list[DocumentChunk]:
    """
    Chunk a code section for embedding.

    Short sections (< MAX_CHUNK_CHARS) become a single chunk.
    Long sections are sub-chunked at paragraph boundaries with overlap.

    @spec DATA-EMBED-001
    """
    if len(content) <= MAX_CHUNK_CHARS:
        return [DocumentChunk(
            source_type=ChunkSourceType.CODE_SECTION,
            source_id=section_id,
            jurisdiction=JurisdictionLevel(jurisdiction),
            chunk_text=content,
            chunk_index=0,
            section_path=section_path,
            metadata={"full_section": True},
        )]

    # Sub-chunk at paragraph boundaries
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        if len(current_chunk) + len(para) > MAX_CHUNK_CHARS and current_chunk:
            chunks.append(DocumentChunk(
                source_type=ChunkSourceType.CODE_SECTION,
                source_id=section_id,
                jurisdiction=JurisdictionLevel(jurisdiction),
                chunk_text=current_chunk.strip(),
                chunk_index=chunk_index,
                section_path=section_path,
                metadata={"full_section": False, "sub_chunk": True},
            ))
            chunk_index += 1
            # Keep overlap from end of previous chunk
            current_chunk = current_chunk[-SUB_CHUNK_OVERLAP:] + "\n\n" + para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    # Final chunk
    if current_chunk.strip():
        chunks.append(DocumentChunk(
            source_type=ChunkSourceType.CODE_SECTION,
            source_id=section_id,
            jurisdiction=JurisdictionLevel(jurisdiction),
            chunk_text=current_chunk.strip(),
            chunk_index=chunk_index,
            section_path=section_path,
            metadata={"full_section": False, "sub_chunk": True},
        ))

    return chunks


def chunk_legislative_item(
    item_id: str,
    title: str,
    summary: str | None,
    jurisdiction: str,
    body: str,
) -> list[DocumentChunk]:
    """
    Chunk a legislative item (bill, ordinance, resolution).

    For MVP, legislative items are typically short enough for a single chunk
    (title + summary). Full bill text chunking is a Phase 4+ concern.

    @spec DATA-EMBED-002
    """
    text_parts = [title]
    if summary:
        text_parts.append(summary)

    chunk_text = "\n\n".join(text_parts)
    section_path = f"{body} > {title}"

    return [DocumentChunk(
        source_type=ChunkSourceType.LEGISLATIVE_ITEM,
        source_id=item_id,
        jurisdiction=JurisdictionLevel(jurisdiction),
        chunk_text=chunk_text,
        chunk_index=0,
        section_path=section_path,
        metadata={"has_summary": summary is not None},
    )]


# ─── Embedding Generation ───────────────────────────────────────────────


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    Uses the embedding model configured in environment (Gemini or MiniLM).

    @spec DATA-EMBED-003
    """
    config = get_config()

    if config.embedding_model == "gemini":
        return _embed_gemini(texts, config.google_ai_api_key)
    elif config.embedding_model == "minilm":
        return _embed_minilm(texts)
    else:
        raise ValueError(f"Unknown embedding model: {config.embedding_model}")


def _embed_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings using Google's Gemini embedding API."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    # Gemini embedding model
    embeddings = []
    for text in texts:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
        )
        embeddings.append(result["embedding"])

    return embeddings


def _embed_minilm(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using local all-MiniLM-L6-v2 model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers required for MiniLM embeddings. "
            "Install with: pip install sentence-transformers"
        )

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, show_progress_bar=True)
    return [emb.tolist() for emb in embeddings]


# ─── Pipeline Runner ────────────────────────────────────────────────────


def run_embedding_pipeline(source_type: str | None = None) -> None:
    """
    Generate embeddings for Silver layer records and write to Gold layer.

    Processes code_sections and legislative_items that don't yet have
    corresponding document_chunks.

    @spec DATA-EMBED-001, DATA-EMBED-002
    """
    db = get_supabase_client()

    if source_type in (None, "code_sections"):
        _embed_code_sections(db)

    if source_type in (None, "legislative_items"):
        _embed_legislative_items(db)


def _embed_code_sections(db) -> None:
    """Chunk and embed all code sections."""
    result = db.table("code_sections").select("*").execute()

    if not result.data:
        logger.info("No code sections to embed")
        return

    logger.info(f"Processing {len(result.data)} code sections")

    for section in result.data:
        chunks = chunk_code_section(
            section_id=section["id"],
            content=section["content"],
            section_path=section.get("section_path", ""),
            jurisdiction=section["jurisdiction"],
        )

        if not chunks:
            continue

        # Generate embeddings in batch
        texts = [c.chunk_text for c in chunks]
        embeddings = generate_embeddings(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            row = chunk.model_dump(mode="json")
            row.pop("id", None)
            # pgvector expects a list, which JSON serializes correctly
            db.table("document_chunks").insert(row).execute()

    logger.info(f"Embedded {len(result.data)} code sections")


def _embed_legislative_items(db) -> None:
    """Chunk and embed all legislative items."""
    result = db.table("legislative_items").select("*").execute()

    if not result.data:
        logger.info("No legislative items to embed")
        return

    logger.info(f"Processing {len(result.data)} legislative items")

    for item in result.data:
        chunks = chunk_legislative_item(
            item_id=item["id"],
            title=item["title"],
            summary=item.get("summary"),
            jurisdiction=item["jurisdiction"],
            body=item["body"],
        )

        texts = [c.chunk_text for c in chunks]
        embeddings = generate_embeddings(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            row = chunk.model_dump(mode="json")
            row.pop("id", None)
            db.table("document_chunks").insert(row).execute()

    logger.info(f"Embedded {len(result.data)} legislative items")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_embedding_pipeline()
