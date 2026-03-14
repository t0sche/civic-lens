"""
LegiScan API client for Maryland state legislative data.

Serves as both a supplementary data source and fallback for Open States.
LegiScan provides full bill text, roll call votes, and amendment tracking
that Open States may not have.

API docs: https://legiscan.com/legiscan

@spec INGEST-API-003, INGEST-API-004
"""

import json
import logging
from typing import Any

import requests

from src.lib.config import get_config
from src.lib.supabase import (
    get_supabase_client,
    upsert_bronze_document,
    start_ingestion_run,
    complete_ingestion_run,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.legiscan.com"
MARYLAND_STATE_ID = 20  # LegiScan state ID for Maryland


class LegiScanClient:
    """
    Client for the LegiScan API.

    Free tier: 30,000 queries/month. Supports bill search, detail,
    full text, roll calls, and bulk session datasets.
    """

    def __init__(self):
        config = get_config()
        self.api_key = config.legiscan_api_key
        self.session = requests.Session()

    def _get(self, params: dict[str, Any]) -> dict:
        """Make an authenticated API request."""
        params["key"] = self.api_key
        response = self.session.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "ERROR":
            raise RuntimeError(f"LegiScan API error: {data.get('alert', {}).get('message', 'unknown')}")
        return data

    def get_session_list(self) -> list[dict]:
        """Get available Maryland legislative sessions."""
        data = self._get({"op": "getSessionList", "state": "MD"})
        return data.get("sessions", [])

    def get_master_list(self, session_id: int) -> dict:
        """
        Get the master list of all bills for a session.
        Returns dict keyed by bill_id with summary metadata.
        """
        data = self._get({"op": "getMasterList", "id": session_id})
        return data.get("masterlist", {})

    def get_bill(self, bill_id: int) -> dict:
        """Get full bill detail including history, sponsors, texts, votes."""
        data = self._get({"op": "getBill", "id": bill_id})
        return data.get("bill", {})

    def get_bill_text(self, doc_id: int) -> dict:
        """Get the full text of a bill document."""
        data = self._get({"op": "getBillText", "id": doc_id})
        return data.get("text", {})

    def search_bills(self, query: str, state: str = "MD", page: int = 1) -> dict:
        """Search bills by keyword."""
        data = self._get({
            "op": "search",
            "state": state,
            "query": query,
            "page": page,
        })
        return data.get("searchresult", {})


def ingest_legiscan_bills(session_id: int | None = None) -> None:
    """
    Ingest Maryland bills from LegiScan into the Bronze layer.

    If session_id is not provided, uses the most recent session.

    @spec INGEST-API-003
    """
    client = LegiScanClient()
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "legiscan")

    try:
        # Get current session if not specified
        if session_id is None:
            sessions = client.get_session_list()
            if not sessions:
                raise RuntimeError("No Maryland sessions found on LegiScan")
            session_id = sessions[0]["session_id"]
            logger.info(f"Using most recent session: {sessions[0].get('session_name', session_id)}")

        # Get master bill list for the session
        master_list = client.get_master_list(session_id)
        fetched = 0

        for key, bill_summary in master_list.items():
            if key == "session":
                continue  # Skip session metadata entry

            bill_id = bill_summary.get("bill_id")
            if not bill_id:
                continue

            # Fetch full bill detail
            bill_detail = client.get_bill(bill_id)
            raw_content = json.dumps(bill_detail, default=str)

            upsert_bronze_document(
                db,
                source="legiscan",
                source_id=str(bill_id),
                document_type="bill",
                raw_content=raw_content,
                raw_metadata={
                    "bill_number": bill_detail.get("bill_number", ""),
                    "session_id": session_id,
                    "state": "MD",
                },
                url=bill_detail.get("url"),
            )
            fetched += 1
            logger.info(f"Ingested LegiScan bill {bill_detail.get('bill_number', bill_id)}")

        complete_ingestion_run(db, run_id, records_fetched=fetched)
        logger.info(f"LegiScan ingestion complete: {fetched} bills fetched")

    except Exception as e:
        logger.error(f"LegiScan ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_legiscan_bills()
