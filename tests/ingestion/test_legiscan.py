"""
Tests for the LegiScan API client.

Uses the `responses` library to mock HTTP requests.

@spec INGEST-API-010, INGEST-API-011, INGEST-API-012, INGEST-API-013
"""

import datetime
import json

import pytest
import responses

import src.ingestion.clients.legiscan as legiscan_module
from src.ingestion.clients.legiscan import (
    BASE_URL,
    LEGISCAN_STATE_ID,
    MONTHLY_QUERY_LIMIT,
    LegiScanClient,
    LegiScanError,
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a LegiScanClient with a test API key and isolated cache directory."""
    monkeypatch.setenv("LEGISCAN_API_KEY", "test-legiscan-key")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    # Patch the module-level CACHE_DIR so the client uses an isolated tmp directory
    cache_dir = tmp_path / "legiscan_cache"
    monkeypatch.setattr(legiscan_module, "CACHE_DIR", cache_dir)
    return LegiScanClient()


def _ok_response(payload: dict) -> dict:
    """Wrap a payload in a standard LegiScan OK envelope."""
    return {"status": "OK", **payload}


def _error_response(message: str = "Invalid API Key") -> dict:
    """Return a LegiScan ERROR envelope."""
    return {"status": "ERROR", "alert": {"message": message}}


def _mock_session_list() -> dict:
    return _ok_response({
        "sessions": [
            {
                "session_id": 1900,
                "session_name": "2026 Regular Session",
                "state_id": LEGISCAN_STATE_ID,
                "year_start": 2026,
                "year_end": 2026,
            },
            {
                "session_id": 1800,
                "session_name": "2025 Regular Session",
                "state_id": LEGISCAN_STATE_ID,
                "year_start": 2025,
                "year_end": 2025,
            },
        ]
    })


def _mock_master_list_raw(session_id: int = 1900) -> dict:
    return _ok_response({
        "masterlist": {
            "session": {"session_id": session_id},
            "12345": {"bill_id": 12345, "change_hash": "aabbcc"},
            "12346": {"bill_id": 12346, "change_hash": "ddeeff"},
        }
    })


def _mock_bill(bill_id: int = 12345) -> dict:
    return _ok_response({
        "bill": {
            "bill_id": bill_id,
            "bill_number": "SB 100",
            "bill_type_id": 1,
            "bill_type": "B",
            "title": "Property Tax Relief Act",
            "description": "A bill to provide property tax relief for residents.",
            "state": "MD",
            "status": 1,
            "status_desc": "Introduced",
            "status_date": "2026-01-15",
            "url": "https://legiscan.com/MD/bill/SB100/2026",
            "state_link": "https://mgaleg.maryland.gov/mgawebsite/Legislation/Details/SB0100",
            "intro_date": "2026-01-15",
            "last_action_date": "2026-02-01",
            "last_action": "Referred to Budget and Taxation",
            "change_hash": "aabbcc",
            "sponsors": [
                {"people_id": 123, "name": "Test Senator", "sponsor_type_desc": "Primary Sponsor"}
            ],
            "subjects": [
                {"subject_id": 1, "subject_name": "Taxation"}
            ],
        }
    })


# ─── Session List ────────────────────────────────────────────────────────


@responses.activate
def test_get_session_list_returns_sessions(client):
    """get_session_list returns a list of sessions for the configured state."""
    responses.add(responses.GET, BASE_URL, json=_mock_session_list(), status=200)

    sessions = client.get_session_list()
    assert len(sessions) == 2
    assert sessions[0]["session_id"] == 1900
    assert sessions[0]["session_name"] == "2026 Regular Session"


@responses.activate
def test_get_session_list_sends_api_key(client):
    """API key is sent as a query parameter on every request."""
    responses.add(responses.GET, BASE_URL, json=_mock_session_list(), status=200)

    client.get_session_list()
    assert "key=test-legiscan-key" in responses.calls[0].request.url


@responses.activate
def test_get_session_list_uses_cache_on_second_call(client):
    """Session list is served from local cache on the second call (no extra query)."""
    responses.add(responses.GET, BASE_URL, json=_mock_session_list(), status=200)

    client.get_session_list()
    client.get_session_list()

    # Only one actual HTTP request should have been made
    assert len(responses.calls) == 1


# ─── Bill Fetching ───────────────────────────────────────────────────────


@responses.activate
def test_get_bill_returns_bill_detail(client):
    """get_bill returns full bill detail for a given bill_id."""
    responses.add(responses.GET, BASE_URL, json=_mock_bill(12345), status=200)

    bill = client.get_bill(12345)
    assert bill["bill_number"] == "SB 100"
    assert bill["title"] == "Property Tax Relief Act"
    assert bill["status"] == 1


@responses.activate
def test_get_bill_sends_correct_op(client):
    """get_bill sends op=getBill and the correct bill id."""
    responses.add(responses.GET, BASE_URL, json=_mock_bill(12345), status=200)

    client.get_bill(12345)
    url = responses.calls[0].request.url
    assert "op=getBill" in url
    assert "id=12345" in url


@responses.activate
def test_get_bill_uses_cache_on_second_call(client):
    """Bill detail is served from cache on subsequent calls for the same bill_id."""
    responses.add(responses.GET, BASE_URL, json=_mock_bill(12345), status=200)

    client.get_bill(12345)
    client.get_bill(12345)

    assert len(responses.calls) == 1


# ─── Master List / Change Detection ─────────────────────────────────────


@responses.activate
def test_get_changed_bills_returns_all_on_first_run(client):
    """On first run (no stored hashes), all bills in master list are returned as changed."""
    responses.add(responses.GET, BASE_URL, json=_mock_master_list_raw(), status=200)

    changed = client.get_changed_bills(1900)
    assert set(changed) == {12345, 12346}


@responses.activate
def test_get_changed_bills_skips_unchanged(client):
    """Bills with unchanged change_hash are not returned on subsequent runs."""
    responses.add(responses.GET, BASE_URL, json=_mock_master_list_raw(), status=200)
    responses.add(responses.GET, BASE_URL, json=_mock_master_list_raw(), status=200)

    # First run: all bills are "changed"
    client.get_changed_bills(1900)

    # Second run with same hashes: nothing should be returned
    changed = client.get_changed_bills(1900)
    assert changed == []


# ─── Error Handling ──────────────────────────────────────────────────────


@responses.activate
def test_api_error_status_raises_legiscan_error(client):
    """When the API returns status=ERROR, LegiScanError is raised."""
    responses.add(
        responses.GET,
        BASE_URL,
        json=_error_response("Invalid API Key"),
        status=200,
    )
    with pytest.raises(LegiScanError, match="Invalid API Key"):
        client.get_session_list()


@responses.activate
def test_http_error_raises_exception(client):
    """HTTP-level errors (4xx/5xx) propagate as exceptions."""
    responses.add(responses.GET, BASE_URL, json={}, status=500)

    with pytest.raises(Exception):
        client.get_session_list()


# ─── Query Budget Tracking ───────────────────────────────────────────────


@responses.activate
def test_query_count_increments_per_request(client):
    """queries_used increments by one for each API call made."""
    responses.add(responses.GET, BASE_URL, json=_mock_session_list(), status=200)
    responses.add(responses.GET, BASE_URL, json=_mock_master_list_raw(), status=200)

    assert client.queries_used == 0
    client.get_session_list()
    assert client.queries_used == 1
    client.get_master_list_raw(1900)
    assert client.queries_used == 2


def test_budget_exhausted_raises_legiscan_error(client):
    """Attempting a request when the monthly budget is exhausted raises LegiScanError."""
    current_month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    budget_data = {
        "month": current_month,
        "count": MONTHLY_QUERY_LIMIT,
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    client._budget_file.write_text(json.dumps(budget_data))
    client._load_query_budget()

    with pytest.raises(LegiScanError, match="budget exhausted"):
        client.get_session_list()


@responses.activate
def test_queries_remaining_decrements(client):
    """queries_remaining decrements as API calls are made."""
    responses.add(responses.GET, BASE_URL, json=_mock_session_list(), status=200)

    initial = client.queries_remaining
    client.get_session_list()
    assert client.queries_remaining == initial - 1

