"""
eCode360 HTML scraper for municipal and county codes.

Extracts the hierarchical structure of codified law from General Code's
eCode360 platform. Municipality codes are configured in civic-lens.config.json.

The scraper preserves section hierarchy (chapter → article → section)
and generates section_path breadcrumbs for RAG retrieval context.

Also fetches "New Laws" PDF documents (bills, executive orders) from
the eCode360 laws page and extracts their text via pdfplumber.

@spec INGEST-SCRAPE-001, INGEST-SCRAPE-002
"""

from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass
from typing import Generator

import cloudscraper
import pdfplumber
from bs4 import BeautifulSoup

from src.lib.config import get_scraper_config
from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

# eCode360 municipality codes
ECODE360_BASE = "https://ecode360.com"
_muni_ecode = get_scraper_config("municipal", "ecode360")
_county_ecode = get_scraper_config("county", "ecode360")
BEL_AIR_CODE = _muni_ecode["code"] if _muni_ecode else None
HARFORD_COUNTY_CODE = _county_ecode["code"] if _county_ecode else None

# Polite crawling: 1 second between requests
REQUEST_DELAY = 1.0


@dataclass
class CodeEntry:
    """A node in the code hierarchy (chapter, article, or section)."""
    title: str
    url: str
    level: str        # "chapter", "article", "section"
    code_id: str      # eCode360 internal ID
    children: list["CodeEntry"] | None = None
    content: str | None = None


@dataclass
class LawEntry:
    """A law/bill/executive order from the eCode360 'New Laws' page."""
    title: str
    pdf_url: str
    law_id: str           # e.g., "LF2639692"
    adopted_date: str | None = None
    subject: str | None = None
    affects: str | None = None
    content: str | None = None


class ECode360Scraper:
    """
    Scraper for eCode360 municipal code sites.

    Strategy:
    1. Fetch the table of contents page to discover all chapters
    2. For each chapter, fetch the full chapter page
    3. Parse individual sections from the chapter HTML
    4. Write each section as a Bronze document with hierarchy metadata
    """

    def __init__(self, municipality_code: str):
        self.municipality_code = municipality_code
        self.base_url = f"{ECODE360_BASE}/{municipality_code}"
        self.session = cloudscraper.create_scraper()

    def fetch_table_of_contents(self) -> list[CodeEntry]:
        """
        Fetch the top-level table of contents for the municipality code.

        Returns a list of CodeEntry objects representing chapters/parts.
        """
        logger.info(f"Fetching TOC for {self.municipality_code}")
        response = self.session.get(self.base_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        chapters = []

        # eCode360 TOC structure: list items with links to chapter pages
        # The exact selectors may need adjustment based on the site version
        toc_links = soup.select("a[href*='/laws/']") or soup.select(".TOC a")

        for link in toc_links:
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not href or not title:
                continue

            # Normalize URL
            if href.startswith("/"):
                href = f"{ECODE360_BASE}{href}"

            # Extract code ID from URL
            code_id = href.rstrip("/").split("/")[-1] if "/" in href else ""

            chapters.append(CodeEntry(
                title=title,
                url=href,
                level="chapter",
                code_id=code_id,
            ))

        logger.info(f"Found {len(chapters)} chapters/parts")
        return chapters

    def fetch_chapter_sections(self, chapter: CodeEntry) -> Generator[CodeEntry, None, None]:
        """
        Fetch all sections within a chapter.

        Yields CodeEntry objects with content populated.
        """
        logger.info(f"Fetching sections for: {chapter.title}")
        time.sleep(REQUEST_DELAY)

        response = self.session.get(chapter.url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # eCode360 section structure: each section is typically in a div
        # with class containing "Section" or similar
        # This parsing logic will need refinement based on actual HTML structure
        section_elements = soup.select(".Section, .section-content, [id^='sec']")

        if not section_elements:
            # Fallback: treat the entire chapter content as one section
            content_div = soup.select_one(".content, .law-content, main")
            if content_div:
                yield CodeEntry(
                    title=chapter.title,
                    url=chapter.url,
                    level="section",
                    code_id=chapter.code_id,
                    content=content_div.get_text(separator="\n", strip=True),
                )
            return

        for elem in section_elements:
            # Extract section title and number
            heading = elem.find(["h1", "h2", "h3", "h4", "strong"])
            title = heading.get_text(strip=True) if heading else chapter.title
            content = elem.get_text(separator="\n", strip=True)

            section_id = elem.get("id", "") or elem.get("data-id", "")

            yield CodeEntry(
                title=title,
                url=f"{chapter.url}#{section_id}" if section_id else chapter.url,
                level="section",
                code_id=section_id or chapter.code_id,
                content=content,
            )

    def fetch_laws(self) -> list[LawEntry]:
        """
        Fetch the 'New Laws' page and discover PDF law documents.

        The laws page lists bills and executive orders with links to PDF files
        following the pattern /laws/LF{id}.pdf.
        """
        laws_url = f"{self.base_url}/laws"
        logger.info(f"Fetching laws page: {laws_url}")

        response = self.session.get(laws_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        laws: list[LawEntry] = []

        # Find all PDF links on the laws page — pattern: /laws/LF{id}.pdf
        pdf_links = soup.find_all("a", href=re.compile(r"/laws/LF\d+\.pdf", re.I))

        for link in pdf_links:
            href = link.get("href", "")
            if href.startswith("/"):
                href = f"{ECODE360_BASE}{href}"

            # Extract law ID from URL (e.g., "LF2639692" from ".../LF2639692.pdf")
            id_match = re.search(r"(LF\d+)\.pdf", href)
            law_id = id_match.group(1) if id_match else href

            title = link.get_text(strip=True)
            # The link text often includes "pdf" suffix from the icon — strip it
            title = re.sub(r"pdf$", "", title).strip()
            if not title:
                title = law_id

            # Try to extract metadata from surrounding table row or list item
            row = link.find_parent("tr")
            adopted_date = None
            subject = None
            affects = None

            if row:
                cells = row.find_all("td")
                # Column layout: [0] Title, [1] Adopted, [2] Subject, [3] Affects
                if len(cells) >= 2:
                    adopted_date = cells[1].get_text(strip=True) or None
                if len(cells) >= 3:
                    subject = cells[2].get_text(strip=True) or None
                if len(cells) >= 4:
                    affects = cells[3].get_text(strip=True) or None

            laws.append(LawEntry(
                title=title,
                pdf_url=href,
                law_id=law_id,
                adopted_date=adopted_date,
                subject=subject,
                affects=affects,
            ))

        logger.info(f"Found {len(laws)} law PDFs")
        return laws

    def fetch_law_pdf_text(self, law: LawEntry) -> str | None:
        """
        Download a law PDF and extract its text content using pdfplumber.

        Returns the extracted text, or None if download or extraction fails.
        """
        try:
            logger.info(f"Downloading PDF: {law.title} ({law.pdf_url})")
            time.sleep(REQUEST_DELAY)

            resp = self.session.get(law.pdf_url, timeout=30)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "pdf" not in content_type and not law.pdf_url.endswith(".pdf"):
                logger.debug(f"Skipping non-PDF response: {content_type}")
                return None

            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)

                if not pages:
                    logger.warning(f"No text extracted from PDF: {law.pdf_url}")
                    return None

                full_text = "\n\n".join(pages)
                logger.info(
                    f"Extracted {len(full_text)} chars from {len(pages)} pages: {law.title}"
                )
                return full_text

        except Exception as e:
            logger.warning(f"Failed to extract PDF {law.pdf_url}: {e}")
            return None


def determine_source_name(municipality_code: str) -> str:
    """Map municipality code to a human-readable source name."""
    names = {}
    if BEL_AIR_CODE:
        names[BEL_AIR_CODE] = "ecode360_belair"
    if HARFORD_COUNTY_CODE:
        names[HARFORD_COUNTY_CODE] = "ecode360_harford"
    return names.get(municipality_code, f"ecode360_{municipality_code.lower()}")


def ingest_municipal_code(municipality_code: str = BEL_AIR_CODE) -> None:
    """
    Main ingestion entry point: scrape a municipal code and write to Bronze layer.

    @spec INGEST-SCRAPE-001
    """
    scraper = ECode360Scraper(municipality_code)
    db = get_supabase_client()
    source_name = determine_source_name(municipality_code)
    run_id = start_ingestion_run(db, source_name)

    try:
        chapters = scraper.fetch_table_of_contents()
        fetched = 0
        new = 0
        updated = 0

        for chapter in chapters:
            for section in scraper.fetch_chapter_sections(chapter):
                if not section.content:
                    continue

                result = upsert_bronze_document(
                    db,
                    source=source_name,
                    source_id=section.code_id or section.url,
                    document_type="code_section",
                    raw_content=section.content,
                    raw_metadata={
                        "chapter": chapter.title,
                        "section_title": section.title,
                        "level": section.level,
                        "municipality_code": municipality_code,
                    },
                    url=section.url,
                )
                fetched += 1
                status = result.get("status", "")
                if status == "new":
                    new += 1
                    logger.info(f"New section: {section.title}")
                elif status == "updated":
                    updated += 1
                    logger.info(f"Updated section: {section.title}")
                else:
                    logger.debug(f"Skipped unchanged section: {section.title}")

        complete_ingestion_run(
            db, run_id,
            records_fetched=fetched,
            records_new=new,
            records_updated=updated,
        )
        logger.info(
            f"eCode360 ingestion complete: {fetched} fetched, {new} new, "
            f"{updated} updated from {municipality_code}"
        )

    except Exception as e:
        logger.error(f"eCode360 ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


def ingest_ecode360_laws(municipality_code: str = HARFORD_COUNTY_CODE) -> None:
    """
    Scrape eCode360 'New Laws' PDFs and write to Bronze layer.

    Downloads each PDF, extracts text via pdfplumber, and stores the
    full text as raw_content with law metadata.
    """
    scraper = ECode360Scraper(municipality_code)
    db = get_supabase_client()
    source_name = f"{determine_source_name(municipality_code)}_laws"
    run_id = start_ingestion_run(db, source_name)

    try:
        laws = scraper.fetch_laws()
        fetched = 0
        new = 0
        updated = 0

        for law in laws:
            pdf_text = scraper.fetch_law_pdf_text(law)

            raw_metadata = {
                "title": law.title,
                "law_id": law.law_id,
                "adopted_date": law.adopted_date,
                "subject": law.subject,
                "affects": law.affects,
                "municipality_code": municipality_code,
                "pdf_url": law.pdf_url,
                "has_pdf": True,
                "pdf_extracted": pdf_text is not None,
            }

            # Use extracted PDF text as content; fall back to metadata summary
            if pdf_text:
                raw_content = pdf_text
            else:
                raw_content = (
                    f"{law.title}\n"
                    f"Adopted: {law.adopted_date or 'Unknown'}\n"
                    f"Subject: {law.subject or 'N/A'}\n"
                    f"Affects: {law.affects or 'N/A'}\n"
                )

            result = upsert_bronze_document(
                db,
                source=source_name,
                source_id=law.law_id,
                document_type="law",
                raw_content=raw_content,
                raw_metadata=raw_metadata,
                url=law.pdf_url,
            )

            fetched += 1
            status = result.get("status", "")
            if status == "new":
                new += 1
                logger.info(f"New law: {law.title}")
            elif status == "updated":
                updated += 1
                logger.info(f"Updated law: {law.title}")
            else:
                logger.debug(f"Unchanged law: {law.title}")

        complete_ingestion_run(
            db, run_id,
            records_fetched=fetched,
            records_new=new,
            records_updated=updated,
        )
        logger.info(
            f"eCode360 laws ingestion complete: {fetched} fetched, {new} new, "
            f"{updated} updated from {municipality_code}"
        )

    except Exception as e:
        logger.error(f"eCode360 laws ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Scrape an eCode360 municipal code")
    available_codes = [c for c in [BEL_AIR_CODE, HARFORD_COUNTY_CODE] if c]
    parser.add_argument(
        "--municipality",
        default=available_codes[0] if available_codes else None,
        choices=available_codes or None,
        help=(
            f"Municipality code to scrape "
            f"(default: {available_codes[0] if available_codes else 'none configured'})"
        ),
    )
    parser.add_argument(
        "--laws",
        action="store_true",
        help="Scrape 'New Laws' PDF documents instead of code sections",
    )
    args = parser.parse_args()
    if args.municipality:
        if args.laws:
            ingest_ecode360_laws(args.municipality)
        else:
            ingest_municipal_code(args.municipality)
    else:
        logger.error("No municipality codes configured in civic-lens.config.json")
