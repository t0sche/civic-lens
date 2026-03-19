"""
Tests for the Harford County bills scraper.

@spec INGEST-SCRAPE-040, INGEST-SCRAPE-041
"""

from src.ingestion.scrapers.harford_bills import _parse_bills_table


def _make_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a minimal HTML table string for testing."""
    header_cells = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        body_rows += f"<tr>{cells}</tr>"
    return (
        f'<table id="GridView1">'
        f"<tr>{header_cells}</tr>"
        f"{body_rows}"
        f"</table>"
    )


def test_parse_bills_table_basic():
    """Parses a minimal table without a Last Action Date column."""
    html = _make_table(
        ["Bill Number", "Title", "Sponsors", "Introduced", "Status", "Last Action"],
        [["CB-001-2024", "Test Bill", "Smith", "01/01/2024", "Introduced", "Referred to committee"]],  # noqa: E501
    )
    bills = _parse_bills_table(html)
    assert len(bills) == 1
    bill = bills[0]
    assert bill.bill_number == "CB-001-2024"
    assert bill.title == "Test Bill"
    assert bill.status == "Introduced"
    assert bill.last_action == "Referred to committee"
    assert bill.last_action_date is None


def test_parse_bills_table_with_last_action_date():
    """Captures last_action_date when a dedicated column is present."""
    headers = [
        "Bill Number", "Title", "Sponsors", "Introduced",
        "Status", "Last Action", "Last Action Date",
    ]
    html = _make_table(
        headers,
        [["CB-002-2024", "Another Bill", "Jones", "02/15/2024", "Passed", "Signed by Executive", "03/01/2024"]],  # noqa: E501
    )
    bills = _parse_bills_table(html)
    assert len(bills) == 1
    bill = bills[0]
    assert bill.bill_number == "CB-002-2024"
    assert bill.last_action == "Signed by Executive"
    assert bill.last_action_date == "03/01/2024"


def test_parse_bills_table_no_date_collision():
    """last_action_date column does not bleed into last_action and vice versa."""
    html = _make_table(
        ["Bill Number", "Title", "Status", "Last Action", "Last Action Date"],
        [["CB-003-2024", "Collision Test", "Active", "Second Reading", "04/10/2024"]],
    )
    bills = _parse_bills_table(html)
    assert len(bills) == 1
    assert bills[0].last_action == "Second Reading"
    assert bills[0].last_action_date == "04/10/2024"


def test_parse_bills_table_empty():
    """Returns empty list when the table has no data rows."""
    html = _make_table(["Bill Number", "Title", "Status"], [])
    assert _parse_bills_table(html) == []


def test_parse_bills_table_no_table():
    """Returns empty list when no bills table is found in the HTML."""
    assert _parse_bills_table("<html><body><p>No table here</p></body></html>") == []


def test_parse_bills_table_sponsors_split():
    """Sponsors are split on commas into a list."""
    html = _make_table(
        ["Bill Number", "Title", "Sponsors", "Status"],
        [["CB-004-2024", "Multi-sponsor", "Smith, Jones, Davis", "Active"]],
    )
    bills = _parse_bills_table(html)
    assert len(bills) == 1
    assert bills[0].sponsors == ["Smith", "Jones", "Davis"]
