"""
CivicLens data models — Pydantic schemas for Silver layer entities.

These models enforce the data contracts defined in the HLD §7 data model.
All ingestion normalizers produce instances of these models before writing
to the Silver layer.
"""

from datetime import date
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ─── Enums matching Postgres types ──────────────────────────────────────


class JurisdictionLevel(str, Enum):
    STATE = "STATE"
    COUNTY = "COUNTY"
    MUNICIPAL = "MUNICIPAL"


class LegislativeStatus(str, Enum):
    INTRODUCED = "INTRODUCED"
    IN_COMMITTEE = "IN_COMMITTEE"
    PASSED_ONE_CHAMBER = "PASSED_ONE_CHAMBER"
    ENACTED = "ENACTED"
    VETOED = "VETOED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"
    TABLED = "TABLED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    EFFECTIVE = "EFFECTIVE"
    UNKNOWN = "UNKNOWN"


class LegislativeType(str, Enum):
    BILL = "BILL"
    ORDINANCE = "ORDINANCE"
    RESOLUTION = "RESOLUTION"
    EXECUTIVE_ORDER = "EXECUTIVE_ORDER"
    ZONING_CHANGE = "ZONING_CHANGE"
    POLICY = "POLICY"
    AGENDA_ITEM = "AGENDA_ITEM"
    OTHER = "OTHER"


class ChunkSourceType(str, Enum):
    LEGISLATIVE_ITEM = "LEGISLATIVE_ITEM"
    CODE_SECTION = "CODE_SECTION"
    MEETING_RECORD = "MEETING_RECORD"
    OTHER = "OTHER"


# ─── Silver Layer Models ────────────────────────────────────────────────


class LegislativeItem(BaseModel):
    """
    Unified model for any tracked legislative/regulatory item.

    Normalizes bills, ordinances, resolutions, executive orders, etc.
    into a common schema regardless of source.

    @spec DATA-SILVER-001
    """

    id: UUID = Field(default_factory=uuid4)
    bronze_id: str | None = None
    source_id: str
    jurisdiction: JurisdictionLevel
    body: str  # e.g., "Maryland General Assembly", "Harford County Council"
    item_type: LegislativeType
    title: str
    summary: str | None = None
    status: LegislativeStatus = LegislativeStatus.UNKNOWN
    introduced_date: date | None = None
    last_action_date: date | None = None
    last_action: str | None = None
    sponsors: list[str] = Field(default_factory=list)
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)


class CodeSection(BaseModel):
    """
    A section of codified law (county code or municipal code).

    Preserves the hierarchical structure of legal codes with
    parent_section_id for tree traversal.

    @spec DATA-SILVER-002
    """

    id: UUID = Field(default_factory=uuid4)
    bronze_id: str | None = None
    jurisdiction: JurisdictionLevel
    code_source: str  # "Harford County Code" or "Town of Bel Air Code"
    chapter: str
    section: str
    title: str
    content: str
    parent_section_id: UUID | None = None
    section_path: str | None = None  # "Town Code > Ch. 165 > §165-23"
    source_url: str | None = None
    effective_date: date | None = None
    last_amended: date | None = None


class MeetingRecord(BaseModel):
    """
    An agenda or minutes document from a government body meeting.

    @spec DATA-SILVER-003
    """

    id: UUID = Field(default_factory=uuid4)
    bronze_id: str | None = None
    jurisdiction: JurisdictionLevel
    body: str  # "Board of Town Commissioners", "Planning Commission", etc.
    meeting_date: date
    record_type: str  # "agenda" or "minutes"
    title: str | None = None
    content: str | None = None  # Extracted text (may be null pre-PDF extraction)
    pdf_url: str | None = None
    source_url: str | None = None


# ─── Gold Layer Models ──────────────────────────────────────────────────


class DocumentChunk(BaseModel):
    """
    A chunk of text with its embedding, ready for RAG retrieval.

    Chunks are created by section-aware splitting (not naive token splitting)
    to preserve legal text semantics.

    @spec DATA-GOLD-001
    """

    id: UUID = Field(default_factory=uuid4)
    source_type: ChunkSourceType
    source_id: str
    jurisdiction: JurisdictionLevel
    chunk_text: str
    chunk_index: int = 0
    section_path: str | None = None
    embedding: list[float] | None = None  # Set during embedding generation
    metadata: dict = Field(default_factory=dict)
