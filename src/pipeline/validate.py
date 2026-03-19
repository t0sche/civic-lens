"""
Silver layer data quality validation.

Validates LegislativeItem and CodeSection records before they are written
to the Silver layer. Rejects records that fail quality checks and logs
each rejection for observability.

@spec DATA-PIPE-040, DATA-PIPE-041, DATA-PIPE-042
"""

from __future__ import annotations

import logging
from typing import Union

from src.lib.models import CodeSection, LegislativeItem

logger = logging.getLogger(__name__)

TITLE_MAX_LEN = 500


def validate_legislative_item(item: LegislativeItem) -> bool:
    """
    Validate a LegislativeItem before Silver layer write.

    Returns True if the record passes all checks; False if it should be
    rejected. Logs a warning for each failed check.

    @spec DATA-PIPE-040, DATA-PIPE-041, DATA-PIPE-042
    """
    valid = True

    # @spec DATA-PIPE-040 — reject empty or oversized title
    if not item.title or not item.title.strip():
        logger.warning(
            "Rejecting LegislativeItem: empty title (source_id=%s, bronze_id=%s)",
            item.source_id,
            item.bronze_id,
        )
        valid = False
    elif len(item.title) > TITLE_MAX_LEN:
        logger.warning(
            "Rejecting LegislativeItem: title exceeds %d chars (source_id=%s, bronze_id=%s)",
            TITLE_MAX_LEN,
            item.source_id,
            item.bronze_id,
        )
        valid = False

    # @spec DATA-PIPE-041 — reject empty source_id
    if not item.source_id or not item.source_id.strip():
        logger.warning(
            "Rejecting LegislativeItem: empty source_id (title=%r, bronze_id=%s)",
            item.title,
            item.bronze_id,
        )
        valid = False

    # @spec DATA-PIPE-042 — reject empty body
    if not item.body or not item.body.strip():
        logger.warning(
            "Rejecting LegislativeItem: empty body (source_id=%s, bronze_id=%s)",
            item.source_id,
            item.bronze_id,
        )
        valid = False

    return valid


def validate_code_section(section: CodeSection) -> bool:
    """
    Validate a CodeSection before Silver layer write.

    Returns True if the record passes all checks; False if it should be
    rejected. Logs a warning for each failed check.

    @spec DATA-PIPE-040, DATA-PIPE-041, DATA-PIPE-042
    """
    valid = True

    # @spec DATA-PIPE-040 — reject empty or oversized title
    if not section.title or not section.title.strip():
        logger.warning(
            "Rejecting CodeSection: empty title (section=%s, bronze_id=%s)",
            section.section,
            section.bronze_id,
        )
        valid = False
    elif len(section.title) > TITLE_MAX_LEN:
        logger.warning(
            "Rejecting CodeSection: title exceeds %d chars (section=%s, bronze_id=%s)",
            TITLE_MAX_LEN,
            section.section,
            section.bronze_id,
        )
        valid = False

    # @spec DATA-PIPE-041 — code sections use section path as the unique identifier;
    # reject if both section and code_source are empty (no usable source_id equivalent)
    if not section.section or not section.section.strip():
        logger.warning(
            "Rejecting CodeSection: empty section identifier (code_source=%s, bronze_id=%s)",
            section.code_source,
            section.bronze_id,
        )
        valid = False

    # @spec DATA-PIPE-042 — reject empty body (content field)
    if not section.content or not section.content.strip():
        logger.warning(
            "Rejecting CodeSection: empty content (section=%s, bronze_id=%s)",
            section.section,
            section.bronze_id,
        )
        valid = False

    return valid


def validate_record(record: Union[LegislativeItem, CodeSection]) -> bool:
    """
    Dispatch validation to the appropriate type-specific validator.

    @spec DATA-PIPE-040, DATA-PIPE-041, DATA-PIPE-042
    """
    if isinstance(record, LegislativeItem):
        return validate_legislative_item(record)
    if isinstance(record, CodeSection):
        return validate_code_section(record)
    logger.warning("validate_record: unknown record type %s", type(record))
    return False
