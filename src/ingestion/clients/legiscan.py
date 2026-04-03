"""
LegiScan API client for state legislative data.

Serves as both a supplementary data source and fallback for Open States.
LegiScan provides full bill text, roll call votes, and amendment tracking
that Open States may not have.

API docs: https://legiscan.com/legiscan
Data licensed under Creative Commons Attribution 4.0 (CC BY 4.0).

Compliance with LegiScan API terms:
  - 30,000 queries/month limit with budget tracking and 80% warning
  - Local JSON caching of all API responses to minimize query spend
  - change_hash comparison to skip unchanged bills
  - dataset_hash comparison to skip unchanged session datasets
  - Status code ("OK" / "ERROR") checked on every response

@spec INGEST-API-010, INGEST-API-011, INGEST-API-012, INGEST-API-013
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.lib.config import get_config, get_state_config
from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.legiscan.com"
_STATE_CONFIG = get_state_config()
LEGISCAN_STATE_ID = _STATE_CONFIG["legiscan_state_id"]
# Backward-compatible alias; prefer LEGISCAN_STATE_ID for new code.
MARYLAND_STATE_ID = LEGISCAN_STATE_ID
_STATE_ABBREV = _STATE_CONFIG["abbrev"]
MONTHLY_QUERY_LIMIT = 30_000
QUERY_WARNING_THRESHOLD = 0.80  # Warn at 80% of monthly limit

# Local cache directory for LegiScan API responses
CACHE_DIR = Path(os.environ.get(
    "LEGISCAN_CACHE_DIR",
    Path(__file__).parent.parent.parent.parent / ".cache" / "legiscan",
))


class LegiScanError(Exception):
    """Raised when the LegiScan API returns an ERROR status."""


class LegiScanBudgetWarning(UserWarning):
    """Warning emitted when API query budget approaches the monthly limit."""


class LegiScanClient:
    """
    Client for the LegiScan API.

    Free tier: 30,000 queries/month. Supports bill search, detail,
    full text, roll calls, and bulk session datasets.

    All responses are cached locally as JSON files to avoid redundant
    queries. Uses LegiScan's change_hash and dataset_hash to detect
    changes and skip fetches when data hasn't been updated.
    """

    def __init__(self):
        config = get_config()
        self.api_key = config.legiscan_api_key
        self.session = requests.Session()
        self._query_count = 0
        self._cache_dir = CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Load persisted query count for current month
        self._budget_file = self._cache_dir / "query_budget.json"
        self._load_query_budget()

    # ─── Query Budget Tracking ────────────────────────────────────────

    def _load_query_budget(self) -> None:
        """Load the current month's query count from disk."""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if self._budget_file.exists():
            try:
                data = json.loads(self._budget_file.read_text())
                if data.get("month") == current_month:
                    self._query_count = data.get("count", 0)
                else:
                    # New month — reset counter
                    self._query_count = 0
                    self._save_query_budget()
            except (json.JSONDecodeError, KeyError):
                self._query_count = 0
        else:
            self._query_count = 0

    def _save_query_budget(self) -> None:
        """Persist the current month's query count to disk."""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        self._budget_file.write_text(json.dumps({
            "month": current_month,
            "count": self._query_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }))

    def _check_budget(self) -> None:
        """Warn if approaching the monthly query limit."""
        if self._query_count >= MONTHLY_QUERY_LIMIT:
            raise LegiScanError(
                f"Monthly query budget exhausted ({self._query_count}/{MONTHLY_QUERY_LIMIT}). "
                "Queries reset on the 1st of each month."
            )
        if self._query_count >= int(MONTHLY_QUERY_LIMIT * QUERY_WARNING_THRESHOLD):
            logger.warning(
                "LegiScan API budget warning: %d/%d queries used (%.0f%%). "
                "Queries reset on the 1st of each month.",
                self._query_count, MONTHLY_QUERY_LIMIT,
                (self._query_count / MONTHLY_QUERY_LIMIT) * 100,
            )

    @property
    def queries_used(self) -> int:
        """Number of API queries used this month."""
        return self._query_count

    @property
    def queries_remaining(self) -> int:
        """Number of API queries remaining this month."""
        return max(0, MONTHLY_QUERY_LIMIT - self._query_count)

    # ─── Local Response Cache ─────────────────────────────────────────

    def _cache_path(self, op: str, **kwargs: Any) -> Path:
        """Generate a deterministic cache file path for an API operation."""
        parts = [op] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        filename = "_".join(str(p) for p in parts) + ".json"
        return self._cache_dir / op / filename

    def _read_cache(self, cache_path: Path) -> dict | None:
        """Read a cached API response from disk. Returns None if not cached."""
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _write_cache(self, cache_path: Path, data: dict) -> None:
        """Write an API response to the local cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, default=str))

    # ─── API Request Layer ────────────────────────────────────────────

    def _get(self, params: dict[str, Any]) -> dict:
        """
        Make an authenticated API request.

        Always checks the status code in the JSON response for "OK" or "ERROR"
        as required by LegiScan API terms.
        """
        self._check_budget()

        params["key"] = self.api_key
        response = self.session.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Track query spend
        self._query_count += 1
        self._save_query_budget()

        # LegiScan API terms: always check status code in JSON response
        status = data.get("status")
        if status == "ERROR":
            alert = data.get("alert", {})
            msg = alert.get("message", "Unknown error") if isinstance(alert, dict) else str(alert)
            raise LegiScanError(f"LegiScan API error: {msg}")
        if status != "OK":
            logger.warning("Unexpected LegiScan status: %s (expected OK or ERROR)", status)

        return data

    # ─── Hash-Based Change Detection ──────────────────────────────────

    def _get_stored_hashes(self, hash_type: str) -> dict[str, str]:
        """Load stored hashes (change_hash or dataset_hash) from cache."""
        hash_file = self._cache_dir / f"{hash_type}_hashes.json"
        if hash_file.exists():
            try:
                return json.loads(hash_file.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_stored_hashes(self, hash_type: str, hashes: dict[str, str]) -> None:
        """Persist hashes to disk for future comparison."""
        hash_file = self._cache_dir / f"{hash_type}_hashes.json"
        hash_file.write_text(json.dumps(hashes))

    # ─── Public API Methods ───────────────────────────────────────────

    def get_session_list(self) -> list[dict]:
        """Get available state legislative sessions."""
        cache_path = self._cache_path("getSessionList", state=_STATE_ABBREV)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached.get("sessions", [])

        data = self._get({"op": "getSessionList", "state": _STATE_ABBREV})
        self._write_cache(cache_path, data)
        return data.get("sessions", [])

    def get_master_list_raw(self, session_id: int) -> dict:
        """
        Get the raw master list for a session including change_hash values.

        Uses getMasterListRaw as recommended by LegiScan API terms for
        efficient polling — returns bill_id + change_hash pairs to detect
        which bills have changed since last fetch.
        """
        data = self._get({"op": "getMasterListRaw", "id": session_id})
        return data.get("masterlist", {})

    def get_master_list(self, session_id: int) -> dict:
        """
        Get the master list of all bills for a session.
        Returns dict keyed by bill_id with summary metadata.
        """
        data = self._get({"op": "getMasterList", "id": session_id})
        return data.get("masterlist", {})

    def get_bill(self, bill_id: int) -> dict:
        """Get full bill detail including history, sponsors, texts, votes."""
        # Check cache first
        cache_path = self._cache_path("getBill", id=bill_id)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached.get("bill", cached)

        data = self._get({"op": "getBill", "id": bill_id})
        self._write_cache(cache_path, data)
        return data.get("bill", {})

    def get_bill_text(self, doc_id: int) -> dict:
        """Get the full text of a bill document (Base64 encoded)."""
        # Check cache — bill text blobs don't need to be downloaded more than once
        cache_path = self._cache_path("getBillText", id=doc_id)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached.get("text", cached)

        data = self._get({"op": "getBillText", "id": doc_id})
        self._write_cache(cache_path, data)
        return data.get("text", {})

    def search_bills(self, query: str, state: str = _STATE_ABBREV, page: int = 1) -> dict:
        """Search bills by keyword."""
        data = self._get({
            "op": "search",
            "state": state,
            "query": query,
            "page": page,
        })
        return data.get("searchresult", {})

    def get_dataset_list(self, session_id: int) -> list[dict]:
        """Get available dataset archives for a session."""
        data = self._get({"op": "getDatasetList", "state": _STATE_ABBREV, "id": session_id})
        return data.get("datasetlist", [])

    def get_dataset(self, dataset_id: int) -> dict:
        """Get a dataset archive (Base64 encoded ZIP)."""
        # Check local cache before downloading (use check_dataset_changed for hash comparison)
        cache_path = self._cache_path("getDataset", id=dataset_id)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached.get("dataset", cached)

        data = self._get({"op": "getDataset", "id": dataset_id})
        self._write_cache(cache_path, data)
        return data.get("dataset", {})

    # ─── Smart Ingestion with Hash Comparison ─────────────────────────

    def get_changed_bills(self, session_id: int) -> list[int]:
        """
        Use getMasterListRaw to detect which bills have changed since
        last fetch, by comparing change_hash values.

        Returns list of bill_ids that need to be re-fetched.

        This is the recommended LegiScan work loop pattern:
        check getMasterListRaw periodically → compare change_hash →
        only spend queries on bills that have actually changed.
        """
        raw_list = self.get_master_list_raw(session_id)
        stored_hashes = self._get_stored_hashes("change")
        changed_bill_ids = []

        for key, entry in raw_list.items():
            if key == "session":
                continue  # Skip session metadata

            bill_id = str(entry.get("bill_id", ""))
            change_hash = entry.get("change_hash", "")
            if not bill_id:
                continue

            # Compare with stored hash — only fetch if hash differs
            if stored_hashes.get(bill_id) != change_hash:
                changed_bill_ids.append(int(bill_id))
                stored_hashes[bill_id] = change_hash

        # Save updated hashes
        self._save_stored_hashes("change", stored_hashes)

        logger.info(
            "change_hash comparison: %d/%d bills changed since last check",
            len(changed_bill_ids),
            sum(1 for k in raw_list if k != "session"),
        )
        return changed_bill_ids

    def check_dataset_changed(self, session_id: int) -> tuple[bool, int | None]:
        """
        Check if the session dataset has changed by comparing dataset_hash.

        Returns (has_changed, dataset_id) tuple.
        """
        datasets = self.get_dataset_list(session_id)
        if not datasets:
            return False, None

        latest = datasets[0]  # Most recent dataset
        dataset_id = latest.get("dataset_id")
        dataset_hash = latest.get("dataset_hash", "")
        session_key = str(session_id)

        stored_hashes = self._get_stored_hashes("dataset")
        if stored_hashes.get(session_key) == dataset_hash:
            logger.info(
                "dataset_hash unchanged for session %s — skipping download",
                session_id,
            )
            return False, dataset_id

        # Update stored hash
        stored_hashes[session_key] = dataset_hash
        self._save_stored_hashes("dataset", stored_hashes)
        return True, dataset_id


def _fetch_legiscan_bill_text(client: LegiScanClient, bill_detail: dict) -> str | None:
    """
    Fetch and decode full bill text from LegiScan API.

    Uses the most recent text document from the bill's texts array.
    Each call costs 1 API query against the monthly budget.
    """
    texts = bill_detail.get("texts", [])
    if not texts:
        return None

    # Get the most recent text document (last in list)
    latest_text = texts[-1]
    doc_id = latest_text.get("doc_id")
    if not doc_id:
        return None

    try:
        text_data = client.get_bill_text(doc_id)
        encoded = text_data.get("doc", "")
        if not encoded:
            return None

        decoded_bytes = base64.b64decode(encoded)
        mime = text_data.get("mime", "text/html")

        if "html" in mime:
            soup = BeautifulSoup(decoded_bytes, "lxml")
            return soup.get_text(separator="\n\n").strip()
        else:
            return decoded_bytes.decode("utf-8", errors="replace").strip()

    except Exception as e:
        bill_num = bill_detail.get("bill_number", "unknown")
        logger.warning(f"Failed to fetch bill text for {bill_num} (doc_id={doc_id}): {e}")
        return None


def ingest_legiscan_bills(session_id: int | None = None) -> None:
    """
    Ingest state bills from LegiScan into the Bronze layer.

    Uses change_hash comparison to only fetch bills that have changed
    since the last ingestion run, minimizing API query spend.

    If session_id is not provided, uses the most recent session.

    @spec INGEST-API-010, INGEST-API-011, INGEST-API-012, INGEST-API-013
    """
    client = LegiScanClient()
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "legiscan")

    try:
        # Get current session if not specified
        if session_id is None:
            sessions = client.get_session_list()
            if not sessions:
                raise RuntimeError(f"No {_STATE_ABBREV} sessions found on LegiScan")
            session_id = sessions[0]["session_id"]
            logger.info(f"Using most recent session: {sessions[0].get('session_name', session_id)}")

        # Use change_hash to find only bills that have changed
        changed_bill_ids = client.get_changed_bills(session_id)

        if not changed_bill_ids:
            logger.info("No bills changed since last check — skipping ingestion")
            complete_ingestion_run(db, run_id, records_fetched=0)
            return

        logger.info(f"Fetching {len(changed_bill_ids)} changed bills (of session {session_id})")
        fetched = 0

        for bill_id in changed_bill_ids:
            # Fetch full bill detail
            bill_detail = client.get_bill(bill_id)
            raw_content = json.dumps(bill_detail, default=str)

            # Fetch full bill text if available (costs 1 API query per bill)
            full_text = _fetch_legiscan_bill_text(client, bill_detail)

            raw_metadata = {
                "bill_number": bill_detail.get("bill_number", ""),
                "session_id": session_id,
                "state": _STATE_ABBREV,
                "change_hash": bill_detail.get("change_hash", ""),
                "legiscan_attribution": "Data provided by LegiScan (CC BY 4.0)",
            }
            if full_text:
                raw_metadata["full_text_extracted"] = True
                raw_metadata["full_text"] = full_text[:100_000]

            upsert_bronze_document(
                db,
                source="legiscan",
                source_id=str(bill_id),
                document_type="bill",
                raw_content=raw_content,
                raw_metadata=raw_metadata,
                url=bill_detail.get("url"),
            )
            fetched += 1
            logger.info(f"Ingested LegiScan bill {bill_detail.get('bill_number', bill_id)}")

        complete_ingestion_run(db, run_id, records_fetched=fetched)
        logger.info(
            f"LegiScan ingestion complete: {fetched} bills fetched. "
            f"API budget: {client.queries_used}/{MONTHLY_QUERY_LIMIT} queries used this month."
        )

    except Exception as e:
        logger.error(f"LegiScan ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_legiscan_bills()
