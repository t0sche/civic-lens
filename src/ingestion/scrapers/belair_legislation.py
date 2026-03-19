"""
Bel Air legislation page scraper.

Parses the Town of Bel Air's legislation tracking page at
belairmd.org/213/Legislation to extract ordinances and resolutions
with their status (Pending, Approved, Tabled, Expired, Rejected).

This is the simplest scraping target — a single HTML table with
links to PDF documents in the CivicPlus DocumentCenter.

@spec INGEST-SCRAPE-010, INGEST-SCRAPE-011, INGEST-SCRAPE-012
@spec INGEST-SCRAPE-013, INGEST-SCRAPE-014, INGEST-SCRAPE-015
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

import requests
from bs4 import BeautifulSoup

from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

LEGISLATION_URL = "https://www.belairmd.org/213/Legislation"
BASE_URL = "https://www.belairmd.org"
REQUEST_DELAY = 1.0


@dataclass
class LegislationEntry:
    """A single ordinance or resolution from the Bel Air legislation page."""
    number: str           # e.g., "Ordinance 743" or "Resolution 2024-01"
    title: str
    status: str           # "Pending", "Approved", "Tabled", "Expired", "Rejected"
    item_type: str        # "ordinance" or "resolution"
    year: str | None = None
    pdf_url: str | None = None
    source_url: str = LEGISLATION_URL


def scrape_legislation_page() -> list[LegislationEntry]:
    """
    Scrape the Bel Air legislation tracking page.

    Returns a list of LegislationEntry objects.
    The page structure is a simple HTML list/table with links to PDFs.
    """
    logger.info(f"Fetching legislation page: {LEGISLATION_URL}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "CivicLens/0.1 (civic transparency project)"
    })

    response = session.get(LEGISLATION_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    entries = []

    # The legislation page uses CivicPlus formatting.
    # Look for content area with legislation listings.
    # Exact selectors will need refinement against the live page.
    content = soup.select_one(".fr-view, .widget-content, #content")

    if not content:
        logger.warning("Could not find content area on legislation page")
        return entries

    # Parse table rows or list items containing legislation
    # CivicPlus typically uses tables or styled divs
    rows = content.select("tr, li, .legislation-item")

    for row in rows:
        text = row.get_text(strip=True)
        if not text:
            continue

        # Extract PDF link if present
        link = row.find("a", href=True)
        pdf_url = None
        if link:
            href = link.get("href", "")
            if href.startswith("/"):
                href = f"{BASE_URL}{href}"
            if "DocumentCenter" in href or href.endswith(".pdf"):
                pdf_url = href

        # Classify as ordinance or resolution
        text_lower = text.lower()
        if "ordinance" in text_lower:
            item_type = "ordinance"
        elif "resolution" in text_lower:
            item_type = "resolution"
        else:
            continue  # Skip non-legislative content

        # Extract status
        status = "UNKNOWN"
        for s in ["approved", "pending", "tabled", "expired", "rejected"]:
            if s in text_lower:
                status = s.upper()
                break

        entries.append(LegislationEntry(
            number=link.get_text(strip=True) if link else text[:50],
            title=text[:200],
            status=status,
            item_type=item_type,
            pdf_url=pdf_url,
        ))

    logger.info(f"Found {len(entries)} legislation entries")
    return entries


def ingest_belair_legislation() -> None:
    """
    Main entry point: scrape Bel Air legislation and write to Bronze layer.

    @spec INGEST-SCRAPE-003
    """
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "belair_legislation")

    try:
        entries = scrape_legislation_page()
        fetched = 0
        new = 0
        updated = 0

        for entry in entries:
            raw_content = json.dumps(asdict(entry), default=str)

            result = upsert_bronze_document(
                db,
                source="belair_legislation",
                source_id=entry.number,
                document_type=entry.item_type,
                raw_content=raw_content,
                raw_metadata={
                    "status": entry.status,
                    "item_type": entry.item_type,
                    "has_pdf": entry.pdf_url is not None,
                },
                url=entry.pdf_url or LEGISLATION_URL,
            )
            fetched += 1
            status = result.get("status", "")
            if status == "new":
                new += 1
            elif status == "updated":
                updated += 1

        complete_ingestion_run(
            db, run_id,
            records_fetched=fetched,
            records_new=new,
            records_updated=updated,
        )
        logger.info(
            f"Bel Air legislation ingestion complete: {fetched} fetched, "
            f"{new} new, {updated} updated"
        )

    except Exception as e:
        logger.error(f"Bel Air legislation ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_belair_legislation()
