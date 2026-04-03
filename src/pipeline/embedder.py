"""
Section-aware chunking and embedding pipeline.

Transforms Silver layer records into vector embeddings stored in the
Gold layer (document_chunks table with pgvector).

Key design decision (HLD D4): Chunks are split by legal section
boundaries, not by token count. This preserves the semantic units
of legal text — statutes, ordinances, and code sections are naturally
bounded by section numbers.

@spec EMBED-CHUNK-001, EMBED-GEN-001, EMBED-WRITE-001
"""

from __future__ import annotations

import hashlib
import logging

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

    @spec EMBED-CHUNK-001, EMBED-CHUNK-002, EMBED-CHUNK-003,
          EMBED-CHUNK-004, EMBED-CHUNK-005, EMBED-CHUNK-006
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

    @spec EMBED-CHUNK-001, EMBED-CHUNK-002
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
    Generate 768-dimensional embeddings using Google Gemini gemini-embedding-001.

    The database schema (pgvector vector(768)) and the RAG query layer both
    require Gemini embeddings. Do not substitute a different model without
    updating the DB schema and the TypeScript query-side embedding call.

    @spec EMBED-GEN-001, EMBED-GEN-003
    """
    config = get_config()

    if config.embedding_model != "gemini":
        raise ValueError(
            f"Unsupported embedding model: {config.embedding_model!r}. "
            f"Only 'gemini' (gemini-embedding-001, 768-dim) is compatible with "
            f"the vector(768) database schema. Set EMBEDDING_MODEL=gemini."
        )

    return _embed_gemini(texts, config.google_ai_api_key)


# Embedding dimension expected by the DB schema and RAG query layer.
EMBEDDING_DIM = 768


def _embed_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings using Google Gemini gemini-embedding-001 (768-dim)."""
    from google import genai

    client = genai.Client(api_key=api_key)

    embeddings = []
    for text in texts:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config={"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": 768},
        )
        values = result.embeddings[0].values
        if len(values) != EMBEDDING_DIM:
            raise RuntimeError(
                f"Expected {EMBEDDING_DIM}-dim embedding, got {len(values)}-dim. "
                f"Check the Gemini embedding model configuration."
            )
        embeddings.append(values)

    return embeddings


def _legitem_source_text(item: dict) -> str:
    """Build the text that gets embedded for a legislative item, for hashing."""
    parts = [item["title"]]
    if item.get("summary"):
        parts.append(item["summary"])
    return "\n\n".join(parts)


# ─── Pipeline Runner ────────────────────────────────────────────────────


def run_embedding_pipeline(source_type: str | None = None) -> None:
    """
    Generate embeddings for Silver layer records and write to Gold layer.

    Processes code_sections and legislative_items that don't yet have
    corresponding document_chunks.

    @spec EMBED-WRITE-001, EMBED-WRITE-002, EMBED-WRITE-003
    """
    db = get_supabase_client()

    if source_type in (None, "code_sections"):
        _embed_code_sections(db)

    if source_type in (None, "legislative_items"):
        _embed_legislative_items(db)


def _get_embedded_source_hashes(db, source_type: str) -> dict[str, str]:
    """Return {source_id: content_hash} for sources that already have chunks."""
    result = (
        db.table("document_chunks")
        .select("source_id,metadata")
        .eq("source_type", source_type)
        .execute()
    )
    hashes: dict[str, str] = {}
    for row in result.data or []:
        sid = row["source_id"]
        meta = row.get("metadata") or {}
        if sid not in hashes and isinstance(meta, dict):
            hashes[sid] = meta.get("content_hash", "")
    return hashes


def _content_hash_for_embedding(text: str) -> str:
    """SHA-256 hash of the text used to generate an embedding."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _delete_chunks_for_source(db, source_type: str, source_id: str) -> None:
    """Delete all existing chunks for a given source record."""
    db.table("document_chunks").delete().eq(
        "source_type", source_type
    ).eq("source_id", source_id).execute()


def _embed_code_sections(db) -> None:
    """Chunk and embed code sections, re-embedding if content has changed."""
    embedded_hashes = _get_embedded_source_hashes(db, ChunkSourceType.CODE_SECTION.value)

    result = db.table("code_sections").select("*").execute()

    if not result.data:
        logger.info("No code sections to embed")
        return

    pending = []
    stale = []
    for s in result.data:
        sid = s["id"]
        current_hash = _content_hash_for_embedding(s["content"])
        if sid not in embedded_hashes:
            pending.append(s)
        elif embedded_hashes[sid] != current_hash:
            stale.append(s)

    if not pending and not stale:
        logger.info(
            f"All {len(result.data)} code sections already embedded, nothing to do"
        )
        return

    if stale:
        logger.info(f"Re-embedding {len(stale)} code sections with changed content")
        for section in stale:
            _delete_chunks_for_source(db, ChunkSourceType.CODE_SECTION.value, section["id"])

    to_embed = pending + stale
    logger.info(
        f"Embedding {len(to_embed)} code sections "
        f"({len(pending)} new, {len(stale)} updated)"
    )

    for section in to_embed:
        chunks = chunk_code_section(
            section_id=section["id"],
            content=section["content"],
            section_path=section.get("section_path", ""),
            jurisdiction=section["jurisdiction"],
        )

        if not chunks:
            continue

        c_hash = _content_hash_for_embedding(section["content"])
        texts = [c.chunk_text for c in chunks]
        embeddings = generate_embeddings(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            chunk.metadata = {**(chunk.metadata or {}), "content_hash": c_hash}
            row = chunk.model_dump(mode="json")
            row.pop("id", None)
            db.table("document_chunks").upsert(
                row, on_conflict="source_type,source_id,chunk_index"
            ).execute()

    logger.info(f"Embedded {len(to_embed)} code sections")


def _embed_legislative_items(db) -> None:
    """Chunk and embed legislative items, re-embedding if content has changed."""
    embedded_hashes = _get_embedded_source_hashes(db, ChunkSourceType.LEGISLATIVE_ITEM.value)

    result = db.table("legislative_items").select("*").execute()

    if not result.data:
        logger.info("No legislative items to embed")
        return

    pending = []
    stale = []
    for i in result.data:
        sid = i["id"]
        source_text = _legitem_source_text(i)
        current_hash = _content_hash_for_embedding(source_text)
        if sid not in embedded_hashes:
            pending.append(i)
        elif embedded_hashes[sid] != current_hash:
            stale.append(i)

    if not pending and not stale:
        logger.info(
            f"All {len(result.data)} legislative items already embedded, nothing to do"
        )
        return

    if stale:
        logger.info(f"Re-embedding {len(stale)} legislative items with changed content")
        for item in stale:
            _delete_chunks_for_source(db, ChunkSourceType.LEGISLATIVE_ITEM.value, item["id"])

    to_embed = pending + stale
    logger.info(
        f"Embedding {len(to_embed)} legislative items "
        f"({len(pending)} new, {len(stale)} updated)"
    )

    for item in to_embed:
        source_text = _legitem_source_text(item)
        c_hash = _content_hash_for_embedding(source_text)

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
            chunk.metadata = {**(chunk.metadata or {}), "content_hash": c_hash}
            row = chunk.model_dump(mode="json")
            row.pop("id", None)
            db.table("document_chunks").upsert(
                row, on_conflict="source_type,source_id,chunk_index"
            ).execute()

    logger.info(f"Embedded {len(to_embed)} legislative items")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_embedding_pipeline()
