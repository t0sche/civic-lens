"""
Municipal legislation page scraper.

Parses the configured municipal legislation tracking page to extract
ordinances and resolutions with their status (Pending, Approved, Tabled,
Expired, Rejected).

This is the simplest scraping target — a single HTML table with
links to PDF documents in the CivicPlus DocumentCenter.

@spec INGEST-SCRAPE-010, INGEST-SCRAPE-011, INGEST-SCRAPE-012,
      INGEST-SCRAPE-013, INGEST-SCRAPE-014, INGEST-SCRAPE-015
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass

import requests
from bs4 import BeautifulSoup

from src.lib.config import get_municipal_config
from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

_municipal = get_municipal_config()
_scraper_cfg = _municipal["scrapers"].get("belair_legislation", {}) if _municipal else {}
LEGISLATION_URL = _scraper_cfg.get("url", "")
BASE_URL = _municipal["website"] if _municipal else ""
REQUEST_DELAY = 1.0


@dataclass
class LegislationEntry:
    """A single ordinance or resolution from the municipal legislation page."""
    number: str           # e.g., "Ordinance 743" or "Resolution 2024-01"
    title: str
    status: str           # "Pending", "Approved", "Tabled", "Expired", "Rejected"
    item_type: str        # "ordinance" or "resolution"
    year: str | None = None
    pdf_url: str | None = None
    source_url: str = LEGISLATION_URL


def scrape_legislation_page() -> list[LegislationEntry]:
    """
    Scrape the municipal legislation tracking page.

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


def fetch_pdf_text(url: str, session: requests.Session) -> tuple[str | None, int]:
    """
    Download a PDF from a URL and extract its text content.

    Uses pdfplumber with OCR fallback for scanned documents.

    Returns (extracted_text, ocr_page_count), or (None, 0) if the download
    or extraction fails.
    """
    from src.ingestion.extractors.pdf_extractor import extract_text

    try:
        logger.info(f"Downloading PDF: {url}")
        resp = session.get(url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not url.endswith(".pdf"):
            logger.debug(f"Skipping non-PDF response: {content_type}")
            return None, 0

        result = extract_text(resp.content)
        logger.info(
            f"Extracted {len(result.text)} chars from {result.page_count} pages "
            f"({result.ocr_page_count} OCR'd): {url}"
        )
        return result.text, result.ocr_page_count

    except requests.RequestException as e:
        logger.warning(f"Failed to download PDF {url}: {e}")
        return None, 0
    except Exception as e:
        logger.warning(f"Failed to extract text from PDF {url}: {e}")
        return None, 0


def ingest_belair_legislation() -> None:
    """
    Main entry point: scrape municipal legislation and write to Bronze layer.

    Downloads PDF documents when available and extracts their text content
    for embedding. Falls back to metadata-only storage when PDFs are
    unavailable or extraction fails.

    @spec INGEST-SCRAPE-010, INGEST-SCRAPE-011, INGEST-SCRAPE-012,
          INGEST-SCRAPE-013, INGEST-SCRAPE-014, INGEST-SCRAPE-015
    """
    if not LEGISLATION_URL:
        logger.info("Municipal legislation scraper not configured — skipping")
        return
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "belair_legislation")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "CivicLens/0.1 (civic transparency project)"
    })

    try:
        entries = scrape_legislation_page()
        fetched = 0
        new = 0
        updated = 0

        for entry in entries:
            # Try to extract full text from PDF (with OCR fallback)
            pdf_text = None
            ocr_page_count = 0
            if entry.pdf_url:
                pdf_text, ocr_page_count = fetch_pdf_text(entry.pdf_url, session)
                time.sleep(REQUEST_DELAY)

            # Use PDF text as raw_content if available, fall back to metadata JSON
            if pdf_text:
                raw_content = pdf_text
                raw_metadata = {
                    "status": entry.status,
                    "item_type": entry.item_type,
                    "has_pdf": True,
                    "pdf_extracted": True,
                    "ocr_pages": ocr_page_count,
                    "pdf_url": entry.pdf_url,
                    "title": entry.title,
                    "number": entry.number,
                }
            else:
                raw_content = json.dumps(asdict(entry), default=str)
                raw_metadata = {
                    "status": entry.status,
                    "item_type": entry.item_type,
                    "has_pdf": entry.pdf_url is not None,
                    "pdf_extracted": False,
                }

            result = upsert_bronze_document(
                db,
                source="belair_legislation",
                source_id=entry.number,
                document_type=entry.item_type,
                raw_content=raw_content,
                raw_metadata=raw_metadata,
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
            f"Municipal legislation ingestion complete: {fetched} fetched, "
            f"{new} new, {updated} updated"
        )

    except Exception as e:
        logger.error(f"Municipal legislation ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_belair_legislation()
