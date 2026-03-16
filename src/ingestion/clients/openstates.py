"""
Open States API v3 client for Maryland state legislative data.

Fetches bills, votes, sponsors, and committee data from the Open States
GraphQL/REST API and writes to the Bronze layer.

API docs: https://docs.openstates.org/api-v3/

@spec INGEST-API-001, INGEST-API-002
"""

from __future__ import annotations

import logging
from typing import Any, Generator

import requests

from src.lib.config import get_config
from src.lib.supabase import (
    get_supabase_client,
    upsert_bronze_document,
    start_ingestion_run,
    complete_ingestion_run,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.openstates.org"
MARYLAND_JURISDICTION = "ocd-jurisdiction/country:us/state:md/government"


class OpenStatesClient:
    """
    Client for the Open States API v3.

    Handles pagination, rate limiting, and Bronze layer persistence.
    """

    def __init__(self):
        config = get_config()
        self.api_key = config.openstates_api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
        })

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict:
        """Make an authenticated GET request with error handling."""
        url = f"{BASE_URL}{endpoint}"
        response = self.session.get(url, params=params or {})
        if not response.ok:
            logger.error(
                "API error %s %s: %s", response.status_code, response.url, response.text
            )
        response.raise_for_status()
        return response.json()

    def fetch_bills(
        self,
        session: str | None = None,
        updated_since: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """
        Fetch Maryland bills with optional filters.

        Args:
            session: Legislative session (e.g., "2025"). Defaults to current.
            updated_since: ISO date string — only return bills updated after this date.
            page: Page number for pagination.
            per_page: Results per page (max 20).

        Returns:
            API response with 'results' list and 'pagination' metadata.
        """
        params: dict[str, Any] = {
            "jurisdiction": MARYLAND_JURISDICTION,
            "page": page,
            "per_page": min(per_page, 20),
            "include": ["abstracts", "actions", "sponsorships", "sources"],
        }
        if session:
            params["session"] = session
        if updated_since:
            params["updated_since"] = updated_since

        return self._get("/bills", params)

    def fetch_all_bills(
        self,
        session: str | None = None,
        updated_since: str | None = None,
    ) -> Generator[dict, None, None]:
        """
        Fetch all Maryland bills with automatic pagination.

        Yields individual bill records.
        """
        page = 1
        while True:
            response = self.fetch_bills(
                session=session,
                updated_since=updated_since,
                page=page,
                per_page=20,
            )
            results = response.get("results", [])
            if not results:
                break

            yield from results

            pagination = response.get("pagination", {})
            if page >= pagination.get("max_page", 1):
                break
            page += 1

    def fetch_bill_detail(self, bill_id: str) -> dict:
        """Fetch full detail for a single bill by Open States ID."""
        return self._get(f"/bills/{bill_id}")


def ingest_state_bills(
    session: str | None = None,
    updated_since: str | None = None,
) -> None:
    """
    Main ingestion entry point: fetch MD bills and write to Bronze layer.

    Called by GitHub Actions on a cron schedule or manually via CLI.

    @spec INGEST-API-001
    """
    client = OpenStatesClient()
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "openstates")

    try:
        fetched = 0
        new = 0
        updated = 0

        for bill in client.fetch_all_bills(session=session, updated_since=updated_since):
            fetched += 1
            bill_id = bill.get("id", "")
            identifier = bill.get("identifier", "unknown")

            # Serialize the full bill JSON as raw content
            import json
            raw_content = json.dumps(bill, default=str)

            result = upsert_bronze_document(
                db,
                source="openstates",
                source_id=bill_id,
                document_type="bill",
                raw_content=raw_content,
                raw_metadata={
                    "identifier": identifier,
                    "session": bill.get("session", ""),
                    "classification": bill.get("classification", []),
                },
                url=bill.get("openstates_url"),
            )

            # TODO: Track new vs. updated based on content_hash comparison
            logger.info(f"Ingested bill {identifier} ({bill_id})")

        complete_ingestion_run(
            db, run_id,
            records_fetched=fetched,
            records_new=new,
            records_updated=updated,
        )
        logger.info(f"Open States ingestion complete: {fetched} bills fetched")

    except Exception as e:
        logger.error(f"Open States ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_state_bills()
