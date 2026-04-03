"""
County council bills tracker scraper.

Scrapes the configured county council bills ASP.NET application.

The site uses classic ASP.NET WebForms with __VIEWSTATE and __EVENTVALIDATION
hidden fields. Each page request requires the ViewState from the previous
response to be echoed back, along with session cookies.

Strategy:
1. GET the Bills page to obtain __VIEWSTATE and __EVENTVALIDATION
2. POST to the same page to trigger the "show all" or paginated results
3. Parse the results table for bill number, title, status, sponsors, dates
4. Write each bill to the Bronze layer as 'harford_bills' source

@spec INGEST-SCRAPE-040, INGEST-SCRAPE-041
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Generator

import requests
from bs4 import BeautifulSoup

from src.lib.config import get_county_config
from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

_county = get_county_config()
_scraper_cfg = _county["scrapers"].get("harford_bills", {}) if _county else {}
BILLS_URL = _scraper_cfg.get("url", "")
REQUEST_DELAY = 1.5   # Polite delay between requests (seconds)
USER_AGENT = "CivicLens/1.0 (civic transparency research; contact: civiclensbair@gmail.com)"


@dataclass
class HarfordBill:
    """A county council bill record."""
    bill_number: str
    title: str
    status: str
    sponsors: list[str] = field(default_factory=list)
    introduced_date: str | None = None
    last_action: str | None = None
    last_action_date: str | None = None
    detail_url: str | None = None


def _get_aspnet_form_state(session: requests.Session) -> dict[str, str]:
    """
    Fetch the Bills page and extract ASP.NET form state tokens.

    Returns a dict with __VIEWSTATE, __VIEWSTATEGENERATOR, and
    __EVENTVALIDATION values needed for POST requests.
    """
    time.sleep(REQUEST_DELAY)
    response = session.get(
        BILLS_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    state = {}

    for field_name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        elem = soup.find("input", {"name": field_name})
        if elem:
            state[field_name] = elem.get("value", "")

    return state


def _parse_bills_table(html: str) -> list[HarfordBill]:
    """
    Parse the bills results table from the page HTML.

    The ASP.NET grid renders as an HTML table with class "GridView" or
    similar. Column order is typically: Bill Number, Title, Sponsors,
    Introduced, Status, Last Action.
    """
    soup = BeautifulSoup(html, "lxml")
    bills = []

    # Look for the results table — ASP.NET uses a GridView control
    table = (
        soup.find("table", {"id": re.compile(r"GridView|gvBills|Bills", re.I)})
        or soup.find("table", class_=re.compile(r"grid|bills", re.I))
    )

    if not table:
        logger.warning("No bills table found on page — HTML structure may have changed")
        return bills

    rows = table.find_all("tr")
    if len(rows) < 2:
        return bills

    # Parse header row to determine column indices
    header_row = rows[0]
    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

    def col_index(name: str) -> int:
        """Find index of a column by partial name match."""
        for i, h in enumerate(headers):
            if name in h:
                return i
        return -1

    bill_num_col = col_index("bill")
    title_col = col_index("title") if col_index("title") >= 0 else col_index("subject")
    sponsor_col = col_index("sponsor")
    intro_col = col_index("introduc") if col_index("introduc") >= 0 else col_index("date")
    status_col = col_index("status")

    # Distinguish between "Last Action" (description) and "Last Action Date"
    # headers is already lowercased (line above), so substring checks are case-safe.
    # Prefer a column that contains "action" but NOT "date" for the text description
    action_col = -1
    action_date_col = -1
    for i, h in enumerate(headers):
        if "action" in h and "date" in h and action_date_col < 0:
            action_date_col = i
        elif "action" in h and "date" not in h and action_col < 0:
            action_col = i
    # Fall back to any "action" or "last" column if specific split not found
    if action_col < 0:
        action_col = col_index("action") if col_index("action") >= 0 else col_index("last")

    for row in rows[1:]:
        cells = row.find_all(["td"])
        if not cells:
            continue

        def cell_text(idx: int) -> str:
            if idx < 0 or idx >= len(cells):
                return ""
            return cells[idx].get_text(strip=True)

        bill_number = cell_text(bill_num_col) if bill_num_col >= 0 else cell_text(0)
        if not bill_number:
            continue

        # Extract detail page link if present
        detail_url = None
        if bill_num_col >= 0 and bill_num_col < len(cells):
            link = cells[bill_num_col].find("a", href=True)
            if link:
                href = link["href"]
                if href.startswith("/"):
                    detail_url = f"https://apps.harfordcountymd.gov{href}"
                elif href.startswith("http"):
                    detail_url = href

        # Parse sponsors (may be comma-separated)
        sponsors_raw = cell_text(sponsor_col) if sponsor_col >= 0 else ""
        sponsors = [s.strip() for s in sponsors_raw.split(",") if s.strip()]

        bills.append(HarfordBill(
            bill_number=bill_number,
            title=cell_text(title_col) if title_col >= 0 else "",
            status=cell_text(status_col) if status_col >= 0 else "Unknown",
            sponsors=sponsors,
            introduced_date=cell_text(intro_col) if intro_col >= 0 else None,
            last_action=cell_text(action_col) if action_col >= 0 else None,
            last_action_date=cell_text(action_date_col) if action_date_col >= 0 else None,
            detail_url=detail_url,
        ))

    return bills


def fetch_all_bills(session: requests.Session) -> Generator[HarfordBill, None, None]:
    """
    Fetch all county council bills, handling ASP.NET pagination.

    Yields HarfordBill objects as they are discovered.
    """
    # Initial GET to obtain form state
    form_state = _get_aspnet_form_state(session)

    # POST to request the full listing (show all records or first page)
    # The exact control IDs may vary — common patterns for ASP.NET WebForms
    post_data = {
        "__VIEWSTATE": form_state.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": form_state.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": form_state.get("__EVENTVALIDATION", ""),
        # Attempt to trigger "show all" via a common ScriptManager pattern
        "ctl00$ContentPlaceHolder1$ddlPageSize": "100",
    }

    time.sleep(REQUEST_DELAY)
    response = session.post(
        BILLS_URL,
        data=post_data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )
    response.raise_for_status()

    bills = _parse_bills_table(response.text)
    logger.info(f"First page: {len(bills)} bills")

    for bill in bills:
        yield bill

    # Handle pagination: look for "next page" postback links
    soup = BeautifulSoup(response.text, "lxml")
    page = 1

    while True:
        # Look for pagination links (ASP.NET LinkButton with page numbers)
        next_page_num = str(page + 1)
        next_link = soup.find("a", string=next_page_num)

        if not next_link:
            break  # No more pages

        # Extract the __doPostBack target for the next page link
        onclick = next_link.get("href", "")
        postback_match = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", onclick)
        if not postback_match:
            break

        event_target = postback_match.group(1)
        event_argument = postback_match.group(2)

        # Re-parse current form state
        viewstate_input = soup.find("input", {"name": "__VIEWSTATE"})
        eventval_input = soup.find("input", {"name": "__EVENTVALIDATION"})

        post_data = {
            "__VIEWSTATE": viewstate_input["value"] if viewstate_input else "",
            "__EVENTVALIDATION": eventval_input["value"] if eventval_input else "",
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": event_argument,
        }

        time.sleep(REQUEST_DELAY)
        response = session.post(
            BILLS_URL,
            data=post_data,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        page_bills = _parse_bills_table(response.text)

        if not page_bills:
            break

        logger.info(f"Page {page + 1}: {len(page_bills)} bills")
        for bill in page_bills:
            yield bill

        page += 1


def _fetch_bill_detail_text(session: requests.Session, detail_url: str) -> str | None:
    """
    Fetch and extract text content from a county bill detail page.

    Returns the extracted text, or None if the fetch or extraction fails.
    """
    try:
        time.sleep(REQUEST_DELAY)
        response = session.get(
            detail_url,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Remove non-content elements
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()

        # Look for main content area (ASP.NET apps often use ContentPlaceHolder)
        content = (
            soup.find("div", {"id": re.compile(r"ContentPlaceHolder|content|main|detail", re.I)})
            or soup.find("main")
            or soup.find("body")
        )

        if not content:
            return None

        text = content.get_text(separator="\n\n").strip()
        # Only return if we got meaningful content (not just nav boilerplate)
        return text if len(text) > 100 else None

    except Exception as e:
        logger.warning(f"Failed to fetch bill detail from {detail_url}: {e}")
        return None


def ingest_harford_bills() -> None:
    """
    Main ingestion entry point: scrape county bills and write to Bronze.

    @spec INGEST-SCRAPE-040
    """
    if not BILLS_URL:
        logger.info("County bills scraper not configured — skipping")
        return
    db = get_supabase_client()
    run_id = start_ingestion_run(db, "harford_bills")

    session = requests.Session()

    try:
        fetched = 0
        new = 0
        updated = 0

        for bill in fetch_all_bills(session):
            # Try to fetch full text from bill detail page
            detail_text = None
            if bill.detail_url:
                detail_text = _fetch_bill_detail_text(session, bill.detail_url)

            raw_content = json.dumps({
                "bill_number": bill.bill_number,
                "title": bill.title,
                "status": bill.status,
                "sponsors": bill.sponsors,
                "introduced_date": bill.introduced_date,
                "last_action": bill.last_action,
                "last_action_date": bill.last_action_date,
                "detail_url": bill.detail_url,
                "jurisdiction": "COUNTY",
                "body": _county["body"] if _county else "County Council",
            })

            raw_metadata: dict = {}
            if detail_text:
                raw_metadata["full_text_extracted"] = True
                raw_metadata["full_text"] = detail_text[:100_000]

            result = upsert_bronze_document(
                db,
                source="harford_bills",
                source_id=bill.bill_number,
                document_type="bill",
                raw_content=raw_content,
                raw_metadata=raw_metadata,
                url=bill.detail_url or BILLS_URL,
            )

            fetched += 1
            status = result.get("status", "")
            if status == "new":
                new += 1
                logger.info(f"New bill: {bill.bill_number} — {bill.title}")
            elif status == "updated":
                updated += 1
                logger.info(f"Updated bill: {bill.bill_number}")
            else:
                logger.debug(f"Unchanged bill: {bill.bill_number}")

        complete_ingestion_run(
            db, run_id,
            records_fetched=fetched,
            records_new=new,
            records_updated=updated,
        )
        logger.info(
            f"County bills ingestion complete: {fetched} fetched, "
            f"{new} new, {updated} updated"
        )

    except Exception as e:
        logger.error(f"County bills ingestion failed: {e}")
        complete_ingestion_run(db, run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_harford_bills()
