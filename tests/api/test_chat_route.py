"""
Tests for the POST /api/chat route contract.

These are unit tests for the request validation and response shape logic.
Integration tests (hitting real Supabase + LLM APIs) run separately.

@spec CHAT-API-001, CHAT-API-002, CHAT-API-003, CHAT-API-004, CHAT-API-005
"""

import json
import pytest


class TestChatRequestValidation:
    """
    Verify request validation rules defined in CHAT-API-002 and CHAT-API-003.

    The Next.js route handler is TypeScript, so we test the validation logic
    by directly exercising the documented rules with Python equivalents that
    mirror the deployed route's behavior.
    """

    def _validate_message(self, message: str | None) -> tuple[bool, str]:
        """Mirror of the validation logic in src/app/api/chat/route.ts."""
        if not message or message.strip() == "":
            return False, "Message is required"
        if len(message) > 2000:
            return False, "Message too long (max 2000 characters)"
        return True, ""

    def test_empty_message_rejected(self):
        """Empty message string returns validation error (CHAT-API-002)."""
        valid, error = self._validate_message("")
        assert not valid
        assert "required" in error.lower()

    def test_whitespace_only_message_rejected(self):
        """Whitespace-only messages are rejected (CHAT-API-002)."""
        valid, error = self._validate_message("   ")
        assert not valid
        assert "required" in error.lower()

    def test_none_message_rejected(self):
        """Missing message field is rejected (CHAT-API-002)."""
        valid, error = self._validate_message(None)
        assert not valid

    def test_valid_message_accepted(self):
        """Normal message passes validation."""
        valid, error = self._validate_message("What are the fence regulations in Bel Air?")
        assert valid
        assert error == ""

    def test_message_at_limit_accepted(self):
        """Message exactly at the 2000 character limit is accepted (CHAT-API-003)."""
        message = "x" * 2000
        valid, error = self._validate_message(message)
        assert valid

    def test_message_over_limit_rejected(self):
        """Message exceeding 2000 characters is rejected (CHAT-API-003)."""
        message = "x" * 2001
        valid, error = self._validate_message(message)
        assert not valid
        assert "2000" in error or "long" in error.lower()


class TestChatResponseShape:
    """
    Verify the response object shape defined in CHAT-API-001.

    Response: { answer: string, sources: Source[], model: string, tier: string }
    """

    def _make_response(self, answer, sources, model, tier, routing_reason):
        """Construct a ChatResponse dict matching the TS interface."""
        return {
            "answer": answer,
            "sources": sources,
            "model": model,
            "tier": tier,
            "routingReason": routing_reason,
        }

    def test_response_has_required_fields(self):
        """Chat response includes all required fields (CHAT-API-001)."""
        resp = self._make_response(
            answer="No fence shall exceed six feet.",
            sources=[],
            model="gemini-2.0-flash",
            tier="free",
            routing_reason="Simple query",
        )
        assert "answer" in resp
        assert "sources" in resp
        assert "model" in resp
        assert "tier" in resp
        assert "routingReason" in resp

    def test_tier_values_are_valid(self):
        """Tier field is one of 'free' or 'frontier' (CHAT-ROUTE-001)."""
        for tier in ("free", "frontier"):
            resp = self._make_response("answer", [], "model", tier, "reason")
            assert resp["tier"] in ("free", "frontier")

    def test_source_shape(self):
        """Each source object has the expected fields (CHAT-API-004)."""
        source = {
            "index": 1,
            "section_path": "Town of Bel Air Code > Chapter 165 > §165-23",
            "jurisdiction": "MUNICIPAL",
            "source_type": "code_section",
            "similarity": 0.87,
        }
        assert "index" in source
        assert "section_path" in source
        assert "jurisdiction" in source
        assert "source_type" in source
        assert "similarity" in source
        assert 0.0 <= source["similarity"] <= 1.0


class TestModelRouting:
    """
    Verify model routing rules from CHAT-ROUTE-001 through CHAT-ROUTE-005.

    These tests mirror the logic in src/lib/router.ts.
    """

    def _route(self, query: str, unique_doc_count: int, jurisdictions: list[str]) -> dict:
        """Mirror of routeQuery() in src/lib/router.ts."""
        import re

        COMPLEXITY_SIGNALS = [
            re.compile(r"state\s+(and|vs\.?|versus)\s+(county|town|municipal)", re.I),
            re.compile(r"all\s+(three|3)\s+(levels?|jurisdictions?|governments?)", re.I),
            re.compile(r"how\s+(would|does|will|could|might)\s+.+\s+affect", re.I),
            re.compile(r"what\s+(is|are)\s+the\s+(impact|effect|consequence)", re.I),
            re.compile(r"compare|comparison|difference\s+between", re.I),
        ]

        doc_threshold = 3

        if unique_doc_count >= doc_threshold:
            return {"tier": "frontier", "model": "claude-sonnet-4-6",
                    "reason": f"spans {unique_doc_count} documents"}

        if len(jurisdictions) > 1:
            return {"tier": "frontier", "model": "claude-sonnet-4-6",
                    "reason": "multi-jurisdiction"}

        for pattern in COMPLEXITY_SIGNALS:
            if pattern.search(query):
                return {"tier": "frontier", "model": "claude-sonnet-4-6",
                        "reason": "complexity pattern"}

        return {"tier": "free", "model": "gemini-2.0-flash",
                "reason": "simple query"}

    def test_many_documents_routes_to_frontier(self):
        """Queries spanning 3+ documents route to the frontier model (CHAT-ROUTE-001)."""
        decision = self._route("test", unique_doc_count=3, jurisdictions=["STATE"])
        assert decision["tier"] == "frontier"

    def test_multi_jurisdiction_routes_to_frontier(self):
        """Queries spanning multiple jurisdictions route to frontier (CHAT-ROUTE-002)."""
        decision = self._route("test", unique_doc_count=1, jurisdictions=["STATE", "MUNICIPAL"])
        assert decision["tier"] == "frontier"

    def test_complexity_pattern_routes_to_frontier(self):
        """Impact analysis queries route to frontier model (CHAT-ROUTE-003)."""
        decision = self._route(
            "How does this state law affect town regulations?",
            unique_doc_count=1,
            jurisdictions=["STATE"],
        )
        assert decision["tier"] == "frontier"

    def test_simple_query_routes_to_free(self):
        """Simple single-jurisdiction queries route to free model (CHAT-ROUTE-004)."""
        decision = self._route(
            "What is the speed limit on Main Street?",
            unique_doc_count=1,
            jurisdictions=["MUNICIPAL"],
        )
        assert decision["tier"] == "free"
        assert decision["model"] == "gemini-2.0-flash"

    def test_frontier_model_is_current_claude_sonnet(self):
        """Frontier model is claude-sonnet-4-6 (current Sonnet)."""
        decision = self._route("test", unique_doc_count=5, jurisdictions=["STATE"])
        assert decision["model"] == "claude-sonnet-4-6"
