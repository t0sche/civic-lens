"""
Supabase client for Python ingestion and pipeline scripts.

Provides typed helpers for Bronze/Silver/Gold layer operations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from src.lib.config import get_config
from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Create an authenticated Supabase client using the service role key."""
    config = get_config()
    return create_client(config.supabase_url, config.supabase_service_key)


def content_hash(content: str) -> str:
    """SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ─── Query Helpers ─────────────────────────────────────────────────────

_PAGE_SIZE = 1000  # PostgREST default row limit


def fetch_all_rows(query) -> list[dict[str, Any]]:
    """Paginate a Supabase query to fetch all rows beyond the 1000-row default."""
    all_rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = query.range(offset, offset + _PAGE_SIZE - 1).execute()
        batch = result.data or []
        all_rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return all_rows


# ─── Bronze Layer Operations ────────────────────────────────────────────


def upsert_bronze_document(
    client: Client,
    *,
    source: str,
    source_id: str,
    document_type: str,
    raw_content: str,
    raw_metadata: dict[str, Any] | None = None,
    url: str | None = None,
) -> dict:
    """
    Insert or update a raw document in the Bronze layer.

    Uses (source, source_id) as the natural key. Skips update if
    content_hash hasn't changed (no-op for unchanged documents).

    Returns a dict with the row data and a "status" key:
      - "skipped"  — content unchanged, no write performed
      - "new"      — first time this (source, source_id) was seen
      - "updated"  — existing record updated with new content
    """
    # @spec INGEST-API-040, INGEST-API-041
    if not raw_content.strip():
        raise ValueError("raw_content must not be empty")
    if not source_id.strip():
        raise ValueError("source_id must not be empty")

    # PostgreSQL cannot store \u0000 in text columns (error 22P05).
    # Strip null bytes from all string content before upserting.
    raw_content = raw_content.replace("\x00", "")
    if raw_metadata:
        raw_metadata = json.loads(json.dumps(raw_metadata).replace("\\u0000", ""))

    new_hash = content_hash(raw_content)

    # Check for an existing record with the same natural key
    existing = (
        client.table("bronze_documents")
        .select("content_hash")
        .eq("source", source)
        .eq("source_id", source_id)
        .limit(1)
        .execute()
    )

    if existing.data and existing.data[0].get("content_hash") == new_hash:
        return {"source": source, "source_id": source_id, "status": "skipped"}

    is_new = not existing.data

    row = {
        "source": source,
        "source_id": source_id,
        "document_type": document_type,
        "raw_content": raw_content,
        "raw_metadata": raw_metadata or {},
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": new_hash,
    }

    result = (
        client.table("bronze_documents")
        .upsert(row, on_conflict="source,source_id")
        .execute()
    )

    row_data = result.data[0] if result.data else row
    row_data["status"] = "new" if is_new else "updated"
    return row_data


# ─── Ingestion Run Tracking ─────────────────────────────────────────────


def start_ingestion_run(client: Client, source: str) -> str:
    """Record the start of an ingestion run. Returns the run ID."""
    result = (
        client.table("ingestion_runs")
        .insert({"source": source, "status": "running"})
        .execute()
    )
    return result.data[0]["id"]


def complete_ingestion_run(
    client: Client,
    run_id: str,
    *,
    records_fetched: int = 0,
    records_new: int = 0,
    records_updated: int = 0,
    error_message: str | None = None,
) -> None:
    """Record the completion (success or failure) of an ingestion run."""
    status = "failed" if error_message else "success"
    client.table("ingestion_runs").update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "records_fetched": records_fetched,
        "records_new": records_new,
        "records_updated": records_updated,
        "error_message": error_message,
    }).eq("id", run_id).execute()
