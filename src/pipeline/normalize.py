"""
Bronze → Silver normalization pipeline.

Transforms raw ingested data from the Bronze layer into the normalized
legislative_item and code_section schemas in the Silver layer.

Each source has a dedicated normalizer function that maps source-specific
fields to the unified data model.

@spec DATA-PIPE-001, DATA-PIPE-002
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Callable

from src.lib.models import (
    CodeSection,
    JurisdictionLevel,
    LegislativeItem,
    LegislativeStatus,
    LegislativeType,
)
from src.lib.config import get_state_config, get_county_config, get_municipal_config, get_scraper_config
from src.lib.supabase import get_supabase_client

logger = logging.getLogger(__name__)


# ─── Status Mapping ─────────────────────────────────────────────────────
# Maps source-specific status strings to the unified LegislativeStatus enum.


OPENSTATES_STATUS_MAP: dict[str, LegislativeStatus] = {
    "introduced": LegislativeStatus.INTRODUCED,
    "referred-to-committee": LegislativeStatus.IN_COMMITTEE,
    "passed-lower-chamber": LegislativeStatus.PASSED_ONE_CHAMBER,
    "passed-upper-chamber": LegislativeStatus.PASSED_ONE_CHAMBER,
    "signed": LegislativeStatus.ENACTED,
    "became-law": LegislativeStatus.ENACTED,
    "vetoed": LegislativeStatus.VETOED,
    "failed": LegislativeStatus.REJECTED,
}

BELAIR_STATUS_MAP: dict[str, LegislativeStatus] = {
    "APPROVED": LegislativeStatus.APPROVED,
    "PENDING": LegislativeStatus.PENDING,
    "TABLED": LegislativeStatus.TABLED,
    "EXPIRED": LegislativeStatus.EXPIRED,
    "REJECTED": LegislativeStatus.REJECTED,
    "UNKNOWN": LegislativeStatus.UNKNOWN,
}

# Maps county council status strings (from the ASP.NET bills tracker) to
# the unified LegislativeStatus enum.
HARFORD_STATUS_MAP: dict[str, LegislativeStatus] = {
    "Introduced": LegislativeStatus.INTRODUCED,
    "Referred to Committee": LegislativeStatus.IN_COMMITTEE,
    "In Committee": LegislativeStatus.IN_COMMITTEE,
    "Passed": LegislativeStatus.ENACTED,
    "Adopted": LegislativeStatus.ENACTED,
    "Enacted": LegislativeStatus.ENACTED,
    "Failed": LegislativeStatus.REJECTED,
    "Withdrawn": LegislativeStatus.REJECTED,
    "Tabled": LegislativeStatus.TABLED,
    "Pending": LegislativeStatus.PENDING,
    "Unknown": LegislativeStatus.UNKNOWN,
}


# ─── Source Normalizers ──────────────────────────────────────────────────


def normalize_openstates_bill(bronze_id: str, raw: dict) -> LegislativeItem:
    """
    Normalize an Open States bill record to a LegislativeItem.

    @spec DATA-PIPE-001
    """
    bill = json.loads(raw) if isinstance(raw, str) else raw

    # Determine status from most recent action classification
    actions = bill.get("actions", [])
    status = LegislativeStatus.UNKNOWN
    last_action_text = None
    last_action_date_str = None

    if actions:
        # Actions are typically in chronological order; take the last one
        latest = actions[-1]
        last_action_text = latest.get("description", "")
        last_action_date_str = latest.get("date", "")

        # Map action classifications to status
        for classification in latest.get("classification", []):
            if classification in OPENSTATES_STATUS_MAP:
                status = OPENSTATES_STATUS_MAP[classification]
                break

    # Extract sponsors
    sponsorships = bill.get("sponsorships", [])
    sponsors = [s.get("name", "") for s in sponsorships if s.get("name")]

    # Determine bill type
    classifications = bill.get("classification", [])
    if "bill" in classifications:
        item_type = LegislativeType.BILL
    elif "resolution" in classifications:
        item_type = LegislativeType.RESOLUTION
    else:
        item_type = LegislativeType.BILL

    # Extract abstract/summary
    abstracts = bill.get("abstracts", [])
    summary = abstracts[0].get("abstract", "") if abstracts else None

    return LegislativeItem(
        bronze_id=bronze_id,
        source_id=bill.get("identifier", ""),
        jurisdiction=JurisdictionLevel.STATE,
        body=get_state_config()["body"],
        item_type=item_type,
        title=bill.get("title", "Untitled"),
        summary=summary,
        status=status,
        introduced_date=_parse_date(bill.get("first_action_date")),
        last_action_date=_parse_date(last_action_date_str),
        last_action=last_action_text,
        sponsors=sponsors,
        source_url=bill.get("openstates_url"),
    )


def normalize_belair_legislation(bronze_id: str, raw: dict) -> LegislativeItem:
    """
    Normalize a municipal legislation entry to a LegislativeItem.

    @spec DATA-PIPE-002
    """
    entry = json.loads(raw) if isinstance(raw, str) else raw

    item_type_str = entry.get("item_type", "other")
    item_type = {
        "ordinance": LegislativeType.ORDINANCE,
        "resolution": LegislativeType.RESOLUTION,
    }.get(item_type_str, LegislativeType.OTHER)

    status_str = entry.get("status", "UNKNOWN")
    status = BELAIR_STATUS_MAP.get(status_str, LegislativeStatus.UNKNOWN)

    return LegislativeItem(
        bronze_id=bronze_id,
        source_id=entry.get("number", ""),
        jurisdiction=JurisdictionLevel.MUNICIPAL,
        body=(get_municipal_config() or {}).get("body", "Municipal Government"),
        item_type=item_type,
        title=entry.get("title", "Untitled"),
        status=status,
        source_url=entry.get("pdf_url") or entry.get("source_url"),
    )


def normalize_harford_bills(bronze_id: str, raw: dict) -> LegislativeItem:
    """
    Normalize a county council bill to a LegislativeItem.

    @spec DATA-PIPE-030, DATA-PIPE-031
    """
    bill = json.loads(raw) if isinstance(raw, str) else raw

    status_str = bill.get("status", "Unknown")
    # Try exact match first, then case-insensitive prefix match
    status = HARFORD_STATUS_MAP.get(status_str)
    if status is None:
        status_lower = status_str.lower()
        for key, val in HARFORD_STATUS_MAP.items():
            if status_lower.startswith(key.lower()):
                status = val
                break
        else:
            status = LegislativeStatus.UNKNOWN

    # County bills may be ordinances or resolutions
    title = bill.get("title", "Untitled")
    title_lower = title.lower()
    if "resolution" in title_lower:
        item_type = LegislativeType.RESOLUTION
    elif "ordinance" in title_lower:
        item_type = LegislativeType.ORDINANCE
    else:
        item_type = LegislativeType.BILL

    return LegislativeItem(
        bronze_id=bronze_id,
        source_id=bill.get("bill_number", ""),
        jurisdiction=JurisdictionLevel.COUNTY,
        body=(get_county_config() or {}).get("body", "County Government"),
        item_type=item_type,
        title=title,
        status=status,
        introduced_date=_parse_date(bill.get("introduced_date")),
        last_action_date=_parse_date(bill.get("last_action_date")),
        last_action=bill.get("last_action"),
        sponsors=bill.get("sponsors", []),
        source_url=bill.get("detail_url"),
    )


def normalize_ecode360_section(bronze_id: str, raw: str, metadata: dict) -> CodeSection:
    """
    Normalize an eCode360 section to a CodeSection.

    @spec DATA-PIPE-020, DATA-PIPE-021, DATA-PIPE-022, DATA-PIPE-023
    """
    municipality_code = metadata.get("municipality_code", "")

    _muni_cfg = get_scraper_config("municipal", "ecode360")
    _cty_cfg = get_scraper_config("county", "ecode360")
    _muni_code = _muni_cfg["code"] if _muni_cfg else None
    _cty_code = _cty_cfg["code"] if _cty_cfg else None

    if _muni_code and municipality_code == _muni_code:
        jurisdiction = JurisdictionLevel.MUNICIPAL
        muni = get_municipal_config()
        code_source = f"{muni['name']} Code" if muni else f"Code {municipality_code}"
    elif _cty_code and municipality_code == _cty_code:
        jurisdiction = JurisdictionLevel.COUNTY
        cty = get_county_config()
        code_source = f"{cty['name']} Code" if cty else f"Code {municipality_code}"
    else:
        jurisdiction = JurisdictionLevel.MUNICIPAL
        code_source = f"Code {municipality_code}"

    chapter = metadata.get("chapter", "Unknown Chapter")
    section_title = metadata.get("section_title", "Untitled Section")
    section_path = f"{code_source} > {chapter} > {section_title}"

    return CodeSection(
        bronze_id=bronze_id,
        jurisdiction=jurisdiction,
        code_source=code_source,
        chapter=chapter,
        section=section_title,
        title=section_title,
        content=raw,
        section_path=section_path,
        source_url=metadata.get("url"),
    )


# ─── Pipeline Runner ────────────────────────────────────────────────────


# Registry of normalizers by Bronze source name
NORMALIZERS: dict[str, Callable] = {
    "openstates": normalize_openstates_bill,
    "belair_legislation": normalize_belair_legislation,
    "harford_bills": normalize_harford_bills,
    # "legiscan": normalize_legiscan_bill,  # TODO (Phase 9)
    # "ecode360_belair": normalize_ecode360_section,  # Uses different signature
    # "ecode360_harford": normalize_ecode360_section,
}


def run_normalization(source: str | None = None) -> None:
    """
    Run Bronze → Silver normalization for the specified source (or all sources).

    Reads unprocessed Bronze records, normalizes them, and upserts to
    the Silver layer.

    @spec DATA-PIPE-001
    """
    db = get_supabase_client()

    # Query Bronze records that need normalization
    query = db.table("bronze_documents").select("*")
    if source:
        query = query.eq("source", source)

    # TODO: Track which Bronze records have been normalized to avoid reprocessing.
    # For MVP, re-normalize everything on each run (idempotent via upsert).
    result = query.execute()

    if not result.data:
        logger.info(f"No Bronze records to normalize for source={source or 'all'}")
        return

    logger.info(f"Normalizing {len(result.data)} Bronze records")

    for row in result.data:
        row_source = row["source"]

        if row_source in ("ecode360_belair", "ecode360_harford"):
            # Code sections use a different normalization path
            section = normalize_ecode360_section(
                bronze_id=row["id"],
                raw=row["raw_content"],
                metadata=row.get("raw_metadata", {}),
            )
            _upsert_code_section(db, section)

        elif row_source in NORMALIZERS:
            normalizer = NORMALIZERS[row_source]
            item = normalizer(bronze_id=row["id"], raw=row["raw_content"])
            _upsert_legislative_item(db, item)

        else:
            logger.warning(f"No normalizer for source: {row_source}")


def _upsert_legislative_item(db, item: LegislativeItem) -> None:
    """Write a LegislativeItem to the Silver layer."""
    row = item.model_dump(mode="json")
    row.pop("id", None)  # Let Postgres generate the ID on insert
    db.table("legislative_items").upsert(
        row,
        on_conflict="source_id,jurisdiction,body",
    ).execute()


def _upsert_code_section(db, section: CodeSection) -> None:
    """Write a CodeSection to the Silver layer."""
    row = section.model_dump(mode="json")
    row.pop("id", None)
    row.pop("parent_section_id", None)  # Handle hierarchy separately
    db.table("code_sections").upsert(
        row,
        on_conflict="code_source,chapter,section",
    ).execute()


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string, returning None on failure."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_normalization()
