"""
eCode360 HTML scraper for municipal and county codes.

Extracts the hierarchical structure of codified law from General Code's
eCode360 platform. Both the Town of Bel Air (BE2811) and Harford County
(HA0904) codes are hosted here.

The scraper preserves section hierarchy (chapter → article → section)
and generates section_path breadcrumbs for RAG retrieval context.

@spec INGEST-SCRAPE-001, INGEST-SCRAPE-002
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Generator

import requests
from bs4 import BeautifulSoup

from src.lib.config import get_config
from src.lib.supabase import (
    get_supabase_client,
    upsert_bronze_document,
    start_ingestion_run,
    complete_ingestion_run,
)

logger = logging.getLogger(__name__)

# eCode360 municipality codes
ECODE360_BASE = "https://ecode360.com"
BEL_AIR_CODE = "BE2811"       # Town of Bel Air
HARFORD_COUNTY_CODE = "HA0904"  # Harford County

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
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CivicLens/0.1 (civic transparency project; contact: github.com/YOUR_USERNAME/civiclens)"
        })

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


def determine_source_name(municipality_code: str) -> str:
    """Map municipality code to a human-readable source name."""
    return {
        BEL_AIR_CODE: "ecode360_belair",
        HARFORD_COUNTY_CODE: "ecode360_harford",
    }.get(municipality_code, f"ecode360_{municipality_code.lower()}")


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

        for chapter in chapters:
            for section in scraper.fetch_chapter_sections(chapter):
                if not section.content:
                    continue

                upsert_bronze_document(
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
                logger.info(f"Ingested: {section.title}")

        complete_ingestion_run(db, run_id, records_fetched=fetched)
        logger.info(f"eCode360 ingestion complete: {fetched} sections from {municipality_code}")

    except Exception as e:
        logger.error(f"eCode360 ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Default: scrape Bel Air town code
    ingest_municipal_code(BEL_AIR_CODE)
