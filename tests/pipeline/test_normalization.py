"""
Tests for the Bronze → Silver normalization pipeline.

@spec DATA-PIPE-001, DATA-PIPE-002, DATA-PIPE-003
"""

import json

from src.lib.models import (
    JurisdictionLevel,
    LegislativeStatus,
    LegislativeType,
)
from src.pipeline.normalize import (
    normalize_belair_legislation,
    normalize_ecode360_section,
    normalize_harford_bills,
    normalize_openstates_bill,
)


class TestNormalizeOpenStatesBill:
    """Tests for Open States → LegislativeItem normalization."""

    def _make_bill(self, **overrides):
        """Helper to create a minimal bill dict."""
        base = {
            "id": "ocd-bill/test-001",
            "identifier": "HB 100",
            "title": "Test Bill",
            "classification": ["bill"],
            "session": "2026",
            "openstates_url": "https://openstates.org/md/bills/2026/HB100/",
            "first_action_date": "2026-01-15",
            "actions": [
                {
                    "date": "2026-01-15",
                    "description": "First Reading",
                    "classification": ["introduction"],
                }
            ],
            "sponsorships": [
                {"name": "Del. Smith", "classification": "primary"}
            ],
            "abstracts": [
                {"abstract": "A test bill about testing."}
            ],
            "sources": [],
        }
        base.update(overrides)
        return base

    def test_basic_fields(self):
        """Core fields are correctly mapped."""
        bill = self._make_bill()
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))

        assert item.source_id == "HB 100"
        assert item.jurisdiction == JurisdictionLevel.STATE
        assert item.body == "Maryland General Assembly"
        assert item.title == "Test Bill"
        assert item.item_type == LegislativeType.BILL

    def test_status_from_action_classification(self):
        """Status is derived from the most recent action's classification."""
        bill = self._make_bill(actions=[
            {"date": "2026-01-15", "description": "Introduced",
             "classification": ["introduction"]},
            {"date": "2026-02-01", "description": "Signed by Governor",
             "classification": ["signed"]},
        ])
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.status == LegislativeStatus.ENACTED

    def test_sponsors_extracted(self):
        """Sponsor names are extracted from sponsorships array."""
        bill = self._make_bill(sponsorships=[
            {"name": "Del. Smith", "classification": "primary"},
            {"name": "Sen. Jones", "classification": "cosponsor"},
        ])
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.sponsors == ["Del. Smith", "Sen. Jones"]

    def test_summary_from_abstracts(self):
        """Summary is taken from the first abstract."""
        bill = self._make_bill()
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.summary == "A test bill about testing."

    def test_no_abstracts_yields_none_summary(self):
        """Missing abstracts result in None summary."""
        bill = self._make_bill(abstracts=[])
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.summary is None

    def test_resolution_type(self):
        """Resolution classification is mapped correctly."""
        bill = self._make_bill(classification=["resolution"])
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.item_type == LegislativeType.RESOLUTION

    def test_unknown_status_default(self):
        """Bills with no recognized action classification default to UNKNOWN."""
        bill = self._make_bill(actions=[
            {"date": "2026-01-15", "description": "Something unusual",
             "classification": ["unusual-action"]},
        ])
        item = normalize_openstates_bill("bronze-123", json.dumps(bill))
        assert item.status == LegislativeStatus.UNKNOWN


class TestNormalizeBelairLegislation:
    """Tests for Bel Air legislation → LegislativeItem normalization."""

    def test_ordinance(self):
        """Ordinance entries are correctly normalized."""
        entry = json.dumps({
            "number": "Ordinance 743",
            "title": "An Ordinance Amending the Town Code",
            "status": "APPROVED",
            "item_type": "ordinance",
            "pdf_url": "https://www.belairmd.org/DocumentCenter/View/1234",
        })
        item = normalize_belair_legislation("bronze-456", entry)

        assert item.source_id == "Ordinance 743"
        assert item.jurisdiction == JurisdictionLevel.MUNICIPAL
        assert item.item_type == LegislativeType.ORDINANCE
        assert item.status == LegislativeStatus.APPROVED
        assert item.body == "Town of Bel Air Board of Commissioners"

    def test_resolution_pending(self):
        """Pending resolutions are normalized with correct status."""
        entry = json.dumps({
            "number": "Resolution 2026-01",
            "title": "A Resolution Regarding Something",
            "status": "PENDING",
            "item_type": "resolution",
        })
        item = normalize_belair_legislation("bronze-789", entry)

        assert item.item_type == LegislativeType.RESOLUTION
        assert item.status == LegislativeStatus.PENDING


class TestNormalizeEcode360Section:
    """Tests for eCode360 → CodeSection normalization."""

    def test_belair_section(self):
        """Bel Air code sections have correct jurisdiction and source."""
        section = normalize_ecode360_section(
            bronze_id="bronze-abc",
            raw="No fence shall exceed six feet in height...",
            metadata={
                "chapter": "Chapter 165 - Development Regulations",
                "section_title": "§165-23 Fences and walls",
                "municipality_code": "BE2811",
            },
        )

        assert section.jurisdiction == JurisdictionLevel.MUNICIPAL
        assert section.code_source == "Town of Bel Air Code"
        assert section.chapter == "Chapter 165 - Development Regulations"
        assert section.section == "§165-23 Fences and walls"
        assert "six feet" in section.content
        expected_path = (
            "Town of Bel Air Code > Chapter 165 - Development Regulations"
            " > §165-23 Fences and walls"
        )
        assert section.section_path == expected_path

    def test_harford_section(self):
        """Harford County code sections have correct jurisdiction."""
        section = normalize_ecode360_section(
            bronze_id="bronze-def",
            raw="The zoning classification shall be...",
            metadata={
                "chapter": "Chapter 267 - Zoning",
                "section_title": "§267-10 Permitted uses",
                "municipality_code": "HA0904",
            },
        )

        assert section.jurisdiction == JurisdictionLevel.COUNTY
        assert section.code_source == "Harford County Code"


class TestNormalizeHarfordBills:
    """Tests for Harford County bills → LegislativeItem normalization."""

    def test_basic_bill(self):
        """County bill is correctly normalized with COUNTY jurisdiction."""
        entry = json.dumps({
            "bill_number": "Bill 23-001",
            "title": "Bill to Amend Zoning Regulations",
            "status": "Introduced",
            "sponsors": ["Councilman Smith", "Councilwoman Jones"],
            "introduced_date": "2023-01-10",
            "last_action": "Referred to Planning Committee",
            "last_action_date": "2023-01-15",
            "detail_url": "https://apps.harfordcountymd.gov/Legislation/Bills/23-001",
        })
        item = normalize_harford_bills("bronze-hc-001", entry)

        assert item.source_id == "Bill 23-001"
        assert item.jurisdiction == JurisdictionLevel.COUNTY
        assert item.body == "Harford County Council"
        assert item.status == LegislativeStatus.INTRODUCED
        assert item.sponsors == ["Councilman Smith", "Councilwoman Jones"]

    def test_resolution_type(self):
        """Bills with 'resolution' in title map to RESOLUTION type."""
        entry = json.dumps({
            "bill_number": "Resolution 23-005",
            "title": "A Resolution Honoring Emergency Services",
            "status": "Passed",
        })
        item = normalize_harford_bills("bronze-hc-002", entry)

        assert item.item_type == LegislativeType.RESOLUTION
        assert item.status == LegislativeStatus.ENACTED

    def test_unknown_status_defaults(self):
        """Unrecognized status strings default to UNKNOWN."""
        entry = json.dumps({
            "bill_number": "Bill 23-010",
            "title": "Some County Bill",
            "status": "Unrecognized Status String",
        })
        item = normalize_harford_bills("bronze-hc-003", entry)
        assert item.status == LegislativeStatus.UNKNOWN
