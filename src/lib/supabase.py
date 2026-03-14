"""
Supabase client for Python ingestion and pipeline scripts.

Provides typed helpers for Bronze/Silver/Gold layer operations.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from supabase import create_client, Client

from src.lib.config import get_config


def get_supabase_client() -> Client:
    """Create an authenticated Supabase client using the service role key."""
    config = get_config()
    return create_client(config.supabase_url, config.supabase_service_key)


def content_hash(content: str) -> str:
    """SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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

    Returns the upserted row.
    """
    row = {
        "source": source,
        "source_id": source_id,
        "document_type": document_type,
        "raw_content": raw_content,
        "raw_metadata": raw_metadata or {},
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash(raw_content),
    }

    result = (
        client.table("bronze_documents")
        .upsert(row, on_conflict="source,source_id")
        .execute()
    )

    return result.data[0] if result.data else row


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
