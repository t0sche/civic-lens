"""
Manual PDF ingestion pipeline.

Accepts a directory of PDFs with optional JSON sidecar files for metadata,
extracts text using pdfplumber, and writes to the Bronze layer via the
existing upsert_bronze_document() helper.

Usage:
    python -m src.ingestion.manual_ingest --dir corpus/harford/
    python -m src.ingestion.manual_ingest --dir corpus/belair/ --dry-run
    python -m src.ingestion.manual_ingest --dir corpus/ --file fy2026-budget.pdf

Folder structure expected:
    corpus/harford/   ← Harford County PDFs + JSON sidecars
    corpus/belair/    ← Town of Bel Air PDFs + JSON sidecars
    corpus/state/     ← Maryland state PDFs + JSON sidecars (future)

Sidecar schema (stem.json alongside stem.pdf):
    {
        "jurisdiction": "COUNTY",          // required: COUNTY | MUNICIPAL | STATE
        "doc_type": "budget",              // required: see DOC_TYPE_VOCAB
        "date": "2025-06-01",             // required: ISO 8601 date
        "source_url": "https://...",       // required: canonical download URL
        "title": "FY2026 Budget",          // optional
        "fiscal_year": "FY2026",           // optional
        "body": "Office of Budget & Mgmt", // optional
        "notes": ""                        // optional
    }

Filename convention fallback (when no sidecar exists):
    {jurisdiction_prefix}-{doc_type}-{YYYY}-{slug}.pdf
    e.g., harford-budget-2026-operating.pdf

@spec INGEST-PDF-010, INGEST-PDF-011, INGEST-PDF-012
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.ingestion.extractors.pdf_extractor import extract_text as extract_pdf
from src.lib.supabase import (
    complete_ingestion_run,
    get_supabase_client,
    start_ingestion_run,
    upsert_bronze_document,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────

SOURCE_NAME = "manual_pdf"

# Valid jurisdiction string literals (matches JurisdictionLevel enum)
JURISDICTION_VALUES = {"COUNTY", "MUNICIPAL", "STATE"}

# Jurisdiction prefix → enum value mapping for filename fallback
JURISDICTION_PREFIX_MAP: dict[str, str] = {
    "harford": "COUNTY",
    "belair": "MUNICIPAL",
    "bel-air": "MUNICIPAL",
    "state": "STATE",
    "md": "STATE",
    "maryland": "STATE",
}

# Valid doc_type vocabulary
DOC_TYPE_VOCAB = {
    "budget",
    "financial_report",
    "zoning",
    "regulation",
    "comprehensive_plan",
    "annual_report",
    "ordinance",
    "resolution",
    "minutes",
    "agenda",
    "policy",
    "other",
}

# ─── Metadata resolution ──────────────────────────────────────────────────


def _load_sidecar(pdf_path: Path) -> dict[str, Any] | None:
    """
    Load the JSON sidecar for a PDF if it exists.

    Returns the parsed dict, or None if the sidecar does not exist.
    The sidecar must share the same stem as the PDF:
        corpus/harford/fy2026-budget.pdf → corpus/harford/fy2026-budget.json
    """
    sidecar_path = pdf_path.with_suffix(".json")
    if not sidecar_path.exists():
        return None
    try:
        with open(sidecar_path) as f:
            data = json.load(f)
        logger.debug(f"Loaded sidecar: {sidecar_path}")
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON sidecar {sidecar_path}: {e}")
        return None


def _parse_filename_convention(pdf_path: Path) -> dict[str, Any]:
    """
    Derive metadata from filename using the convention:
        {jurisdiction_prefix}-{doc_type}-{YYYY}-{slug}.pdf

    Returns a partial metadata dict. Fields not determinable from
    the filename are omitted (caller should fill defaults).
    """
    stem = pdf_path.stem.lower()
    parts = stem.split("-")
    meta: dict[str, Any] = {}

    # Jurisdiction prefix (first token)
    if parts and parts[0] in JURISDICTION_PREFIX_MAP:
        meta["jurisdiction"] = JURISDICTION_PREFIX_MAP[parts[0]]

    # Doc type (second token if it matches vocabulary)
    if len(parts) >= 2 and parts[1].replace("_", "-") in {
        t.replace("_", "-") for t in DOC_TYPE_VOCAB
    }:
        # Normalize hyphen → underscore for matching
        meta["doc_type"] = parts[1].replace("-", "_")

    # Year (any 4-digit YYYY token)
    for part in parts[2:]:
        if re.fullmatch(r"\d{4}", part):
            meta["date"] = part  # Will be normalized to date string
            break

    return meta


def _infer_jurisdiction_from_dir(pdf_path: Path) -> str | None:
    """
    Infer jurisdiction from the immediate parent directory name.

    corpus/harford/ → COUNTY
    corpus/belair/  → MUNICIPAL
    corpus/state/   → STATE
    """
    parent_name = pdf_path.parent.name.lower()
    return JURISDICTION_PREFIX_MAP.get(parent_name)


def _resolve_metadata(pdf_path: Path, sidecar: dict[str, Any] | None) -> dict[str, Any]:
    """
    Resolve final metadata for a PDF by merging sources in priority order:
        1. Explicit sidecar JSON (highest priority)
        2. Filename convention parsing
        3. Directory name inference
        4. Defaults (lowest priority)

    Raises ValueError if required fields cannot be resolved.
    """
    # Start with defaults
    meta: dict[str, Any] = {
        "jurisdiction": None,
        "doc_type": "other",
        "date": None,
        "source_url": None,
        "title": pdf_path.stem.replace("-", " ").replace("_", " ").title(),
        "fiscal_year": None,
        "body": None,
        "notes": None,
    }

    # Apply filename convention
    filename_meta = _parse_filename_convention(pdf_path)
    meta.update({k: v for k, v in filename_meta.items() if v is not None})

    # Apply directory inference (only for jurisdiction if not yet set)
    if not meta["jurisdiction"]:
        dir_jurisdiction = _infer_jurisdiction_from_dir(pdf_path)
        if dir_jurisdiction:
            meta["jurisdiction"] = dir_jurisdiction

    # Apply sidecar (highest priority — overrides everything)
    if sidecar:
        for key, value in sidecar.items():
            if value is not None:
                meta[key] = value

    # Validate required fields
    errors = []

    if not meta["jurisdiction"]:
        errors.append(
            "jurisdiction is required (COUNTY | MUNICIPAL | STATE). "
            "Add a JSON sidecar or use filename prefix: harford-, belair-, state-"
        )
    elif meta["jurisdiction"] not in JURISDICTION_VALUES:
        errors.append(
            f"jurisdiction '{meta['jurisdiction']}' is not valid. "
            f"Must be one of: {', '.join(sorted(JURISDICTION_VALUES))}"
        )

    if not meta["date"]:
        errors.append(
            "date is required (ISO 8601: YYYY-MM-DD or YYYY). "
            "Add a JSON sidecar or include a 4-digit year in the filename."
        )

    if not meta["source_url"]:
        errors.append(
            "source_url is required. Add a JSON sidecar with the canonical download URL."
        )

    if errors:
        raise ValueError(
            f"Missing required metadata for {pdf_path.name}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Normalize date to ISO string
    date_val = meta["date"]
    if isinstance(date_val, str):
        # Accept YYYY, YYYY-MM, YYYY-MM-DD
        if re.fullmatch(r"\d{4}", date_val):
            meta["date"] = f"{date_val}-01-01"
        elif re.fullmatch(r"\d{4}-\d{2}", date_val):
            meta["date"] = f"{date_val}-01"
        # else assume already YYYY-MM-DD
    elif isinstance(date_val, (date, datetime)):
        meta["date"] = date_val.isoformat()[:10]

    return meta


# ─── Ingestion logic ──────────────────────────────────────────────────────


def build_source_id(pdf_path: Path, corpus_dir: Path) -> str:
    """
    Build a stable, namespaced source_id for the Bronze layer.

    Format: manual:{relative_path_without_extension}
    Example: manual:harford/fy2026-operating-budget

    Uses the path relative to corpus_dir to ensure uniqueness across subdirs.
    """
    try:
        relative = pdf_path.relative_to(corpus_dir)
    except ValueError:
        # Fallback if pdf_path is not under corpus_dir
        relative = Path(pdf_path.parent.name) / pdf_path.stem
    return f"manual:{relative.with_suffix('')}"


def ingest_pdf(
    pdf_path: Path,
    corpus_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Ingest a single PDF: resolve metadata, extract text, write to Bronze.

    Returns a result dict with keys: path, source_id, status, error (if any).

    @spec INGEST-PDF-010, INGEST-PDF-011
    """
    result: dict[str, Any] = {
        "path": str(pdf_path),
        "source_id": None,
        "status": "pending",
        "error": None,
    }

    # 1. Load sidecar
    sidecar = _load_sidecar(pdf_path)

    # 2. Resolve metadata
    try:
        meta = _resolve_metadata(pdf_path, sidecar)
    except ValueError as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Metadata error for {pdf_path.name}: {e}")
        return result

    # 3. Build source_id
    source_id = build_source_id(pdf_path, corpus_dir)
    result["source_id"] = source_id

    # 4. Extract PDF text (with OCR fallback for scanned pages)
    try:
        extraction = extract_pdf(pdf_path)
    except RuntimeError as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(str(e))
        return result

    raw_content = extraction.text
    raw_metadata: dict[str, Any] = {
        "jurisdiction": meta["jurisdiction"],
        "doc_type": meta["doc_type"],
        "date": meta["date"],
        "source_url": meta["source_url"],
        "title": meta["title"],
        "page_count": extraction.page_count,
        "ocr_pages": extraction.ocr_page_count,
        "filename": pdf_path.name,
    }
    # Include optional fields if present
    for optional_key in ("fiscal_year", "body", "notes"):
        if meta.get(optional_key):
            raw_metadata[optional_key] = meta[optional_key]

    if dry_run:
        logger.info(
            f"[DRY RUN] Would ingest {pdf_path.name}: "
            f"source_id={source_id}, jurisdiction={meta['jurisdiction']}, "
            f"doc_type={meta['doc_type']}, pages={page_count}, "
            f"chars={len(raw_content)}"
        )
        result["status"] = "dry_run"
        return result

    # 6. Write to Bronze layer
    try:
        db = get_supabase_client()
        upsert_result = upsert_bronze_document(
            db,
            source=SOURCE_NAME,
            source_id=source_id,
            document_type=meta["doc_type"],
            raw_content=raw_content,
            raw_metadata=raw_metadata,
            url=meta["source_url"],
        )
        result["status"] = upsert_result.get("status", "unknown")
        logger.info(
            f"{result['status'].upper()}: {pdf_path.name} → {source_id} "
            f"({page_count} pages, {len(raw_content)} chars)"
        )
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Bronze write failed for {pdf_path.name}: {e}")

    return result


def collect_pdfs(target_dir: Path, filename_filter: str | None = None) -> list[Path]:
    """
    Collect PDF files from target_dir.

    If filename_filter is given, only return the matching file.
    If target_dir contains subdirectories, recurse into them.
    Returns sorted list of absolute paths.
    """
    if filename_filter:
        pdf_path = target_dir / filename_filter
        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")
        return [pdf_path.resolve()]

    # Collect all PDFs, including in immediate subdirectories
    pdfs = sorted(target_dir.rglob("*.pdf"))
    if not pdfs:
        logger.warning(f"No PDF files found in {target_dir}")
    return pdfs


# ─── CLI entry point ──────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion.manual_ingest",
        description=(
            "Ingest PDFs from a local corpus directory into the Bronze layer. "
            "Each PDF must have a JSON sidecar or follow the filename convention "
            "{jurisdiction_prefix}-{doc_type}-{YYYY}-{slug}.pdf."
        ),
    )
    parser.add_argument(
        "--dir",
        required=True,
        metavar="DIR",
        help="Directory containing PDFs (e.g., corpus/harford/ or corpus/)",
    )
    parser.add_argument(
        "--file",
        default=None,
        metavar="FILENAME",
        help="Process only this specific PDF file within --dir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate metadata and extract text but do not write to Bronze layer",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    CLI main function. Returns exit code (0 = success, 1 = partial/total failure).

    @spec INGEST-PDF-012
    """
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    target_dir = Path(args.dir).resolve()
    if not target_dir.exists():
        logger.error(f"Directory does not exist: {target_dir}")
        return 1
    if not target_dir.is_dir():
        logger.error(f"Not a directory: {target_dir}")
        return 1

    # Collect PDFs
    try:
        pdfs = collect_pdfs(target_dir, filename_filter=args.file)
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    if not pdfs:
        logger.info("No PDFs to process.")
        return 0

    logger.info(
        f"{'[DRY RUN] ' if args.dry_run else ''}Processing {len(pdfs)} PDF(s) from {target_dir}"
    )

    # Track ingestion run (skip run tracking in dry-run mode)
    run_id = None
    db = None
    if not args.dry_run:
        try:
            db = get_supabase_client()
            run_id = start_ingestion_run(db, SOURCE_NAME)
        except Exception as e:
            logger.warning(
                f"Could not start ingestion run tracker: {e}. Continuing without tracking."
            )

    # Process each PDF
    results = []
    for pdf_path in pdfs:
        logger.debug(f"Processing: {pdf_path}")
        result = ingest_pdf(pdf_path, corpus_dir=target_dir, dry_run=args.dry_run)
        results.append(result)

    # Summarize
    counts = {
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "dry_run": 0,
        "error": 0,
    }
    for r in results:
        status = r.get("status", "error")
        if status in counts:
            counts[status] += 1
        else:
            counts["error"] += 1

    total = len(results)
    errors = [r for r in results if r.get("status") == "error"]

    if args.dry_run:
        logger.info(
            f"[DRY RUN] Complete: {counts['dry_run']} validated, "
            f"{counts['error']} errors out of {total} PDFs"
        )
    else:
        logger.info(
            f"Ingestion complete: {counts['new']} new, {counts['updated']} updated, "
            f"{counts['skipped']} skipped, {counts['error']} errors "
            f"out of {total} PDFs"
        )

    # Report errors
    if errors:
        logger.error(f"\n{len(errors)} file(s) failed:")
        for r in errors:
            logger.error(f"  {Path(r['path']).name}: {r['error']}")

    # Complete ingestion run
    if run_id and db:
        try:
            complete_ingestion_run(
                db,
                run_id,
                records_fetched=total,
                records_new=counts["new"],
                records_updated=counts["updated"],
                error_message=(
                    f"{counts['error']} PDF(s) failed to ingest" if errors else None
                ),
            )
        except Exception as e:
            logger.warning(f"Could not complete ingestion run tracker: {e}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
