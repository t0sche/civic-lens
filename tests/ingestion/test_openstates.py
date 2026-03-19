"""
Tests for the Open States API client.

Uses the `responses` library to mock HTTP requests.

@spec INGEST-API-001, INGEST-API-002
"""

from urllib.parse import unquote

import pytest
import responses

from src.ingestion.clients.openstates import (
    BASE_URL,
    MARYLAND_JURISDICTION,
    OpenStatesClient,
)


@pytest.fixture
def client(monkeypatch):
    """Create an OpenStatesClient with a test API key."""
    monkeypatch.setenv("OPENSTATES_API_KEY", "test-key-12345")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    return OpenStatesClient()


def _mock_bills_response(page=1, max_page=1, bills=None):
    """Helper to create a mock bills API response."""
    if bills is None:
        bills = [
            {
                "id": "ocd-bill/test-001",
                "identifier": "HB 100",
                "title": "Test Bill - Property Tax Relief",
                "classification": ["bill"],
                "session": "2026",
                "openstates_url": "https://openstates.org/md/bills/2026/HB100/",
                "actions": [
                    {
                        "date": "2026-01-15",
                        "description": "First Reading",
                        "classification": ["introduction"],
                    }
                ],
                "sponsorships": [
                    {"name": "Test Delegate", "classification": "primary"}
                ],
                "abstracts": [
                    {"abstract": "A bill to provide property tax relief for residents."}
                ],
                "sources": [],
            }
        ]
    return {
        "results": bills,
        "pagination": {
            "page": page,
            "per_page": 50,
            "max_page": max_page,
            "total_items": len(bills),
        },
    }


@responses.activate
def test_fetch_bills_returns_results(client):
    """Fetching bills returns a list of bill records."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json=_mock_bills_response(),
        status=200,
    )

    result = client.fetch_bills()
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["identifier"] == "HB 100"


@responses.activate
def test_fetch_bills_sends_api_key(client):
    """API key is sent in the request headers."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json=_mock_bills_response(),
        status=200,
    )

    client.fetch_bills()
    assert responses.calls[0].request.headers["X-API-KEY"] == "test-key-12345"


@responses.activate
def test_fetch_bills_includes_jurisdiction(client):
    """Request includes Maryland jurisdiction parameter."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json=_mock_bills_response(),
        status=200,
    )

    client.fetch_bills()
    assert MARYLAND_JURISDICTION in unquote(responses.calls[0].request.url)


@responses.activate
def test_fetch_all_bills_paginates(client):
    """fetch_all_bills follows pagination to retrieve all pages."""
    # Page 1 of 2
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json=_mock_bills_response(page=1, max_page=2),
        status=200,
    )
    # Page 2 of 2
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json=_mock_bills_response(
            page=2,
            max_page=2,
            bills=[{
                "id": "ocd-bill/test-002",
                "identifier": "SB 200",
                "title": "Second Bill",
                "classification": ["bill"],
                "session": "2026",
                "actions": [],
                "sponsorships": [],
                "abstracts": [],
                "sources": [],
            }],
        ),
        status=200,
    )

    bills = list(client.fetch_all_bills())
    assert len(bills) == 2
    assert bills[0]["identifier"] == "HB 100"
    assert bills[1]["identifier"] == "SB 200"


@responses.activate
def test_fetch_bills_handles_empty_response(client):
    """Empty results list stops pagination."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json={"results": [], "pagination": {"page": 1, "max_page": 1}},
        status=200,
    )

    bills = list(client.fetch_all_bills())
    assert len(bills) == 0


@responses.activate
def test_fetch_bills_raises_on_http_error(client):
    """HTTP errors are raised as exceptions."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/bills",
        json={"error": "unauthorized"},
        status=401,
    )

    with pytest.raises(Exception):
        client.fetch_bills()
