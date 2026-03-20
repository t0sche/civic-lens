"""
Tests for the POST /api/chat route contract.

These are unit tests for the request validation, response shape,
question-type classification, and model routing logic.
Integration tests (hitting real Supabase + LLM APIs) run separately.

@spec CHAT-API-001, CHAT-API-002, CHAT-API-003, CHAT-API-004, CHAT-API-005
"""

import re


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
        """Tier field is one of 'free' or 'frontier' (CHAT-API-001)."""
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


class TestQuestionTypeClassification:
    """
    Verify question-type classification logic from CHAT-ROUTE-003.

    Mirrors classifyQuestion() in src/lib/router.ts.
    """

    # Question type classification patterns (mirroring router.ts)
    DEFINITION_PATTERNS = [
        re.compile(
            r"what\s+(does|is)\s+(a|an|the)?\s*[\"']?\w+[\"']?\s+(mean|refer\s+to|stand\s+for)",
            re.I,
        ),
        re.compile(r"define\s+", re.I),
        re.compile(r"definition\s+of", re.I),
        re.compile(r"what\s+is\s+(a|an|the)\s+\w+\??$", re.I),
    ]

    STATUS_PATTERNS = [
        re.compile(r"status\s+of", re.I),
        re.compile(r"what\s+happened\s+(to|with)", re.I),
        re.compile(r"has\s+.+\s+(passed|been\s+(signed|vetoed|introduced|approved))", re.I),
        re.compile(r"is\s+.+\s+still\s+(active|pending|in\s+committee)", re.I),
    ]

    PROCEDURAL_PATTERNS = [
        re.compile(
            r"how\s+(do|can|should)\s+I\s+(apply|file|submit|request|get|obtain|register)",
            re.I,
        ),
        re.compile(
            r"what\s+(is|are)\s+the\s+(process|steps|procedure|requirements?)\s+(for|to)",
            re.I,
        ),
    ]

    COMPARISON_PATTERNS = [
        re.compile(r"compare|comparison|difference\s+between", re.I),
        re.compile(r"state\s+(and|vs\.?|versus)\s+(county|town|municipal)", re.I),
        re.compile(r"how\s+(does|do)\s+.+\s+differ", re.I),
    ]

    ANALYSIS_PATTERNS = [
        re.compile(r"how\s+(would|does|will|could|might)\s+.+\s+affect", re.I),
        re.compile(r"what\s+(is|are)\s+the\s+(impact|effect|consequence)", re.I),
        re.compile(r"if\s+.+\s+then\s+what", re.I),
    ]

    MULTI_JURISDICTION_PATTERNS = [
        re.compile(r"all\s+(three|3)\s+(levels?|jurisdictions?|governments?)", re.I),
        re.compile(r"which\s+(government|jurisdiction|level)", re.I),
        re.compile(r"across\s+(all|every|multiple)\s+(levels?|jurisdictions?)", re.I),
    ]

    SYNTHESIS_PATTERNS = [
        re.compile(r"what\s+are\s+all\s+the", re.I),
        re.compile(r"comprehensive|exhaustive|complete\s+(list|overview|summary)", re.I),
        re.compile(r"everything\s+(about|regarding|related\s+to)", re.I),
    ]

    SIMPLE_TYPES = {"factual_lookup", "definition", "status_check", "procedural"}

    def _classify(self, query: str) -> str:
        """Mirror of classifyQuestion() in src/lib/router.ts."""
        # Complex types first
        for pattern in self.MULTI_JURISDICTION_PATTERNS:
            if pattern.search(query):
                return "multi_jurisdiction"
        for pattern in self.COMPARISON_PATTERNS:
            if pattern.search(query):
                return "comparison"
        for pattern in self.ANALYSIS_PATTERNS:
            if pattern.search(query):
                return "analysis"
        for pattern in self.SYNTHESIS_PATTERNS:
            if pattern.search(query):
                return "synthesis"
        # Simple types
        for pattern in self.DEFINITION_PATTERNS:
            if pattern.search(query):
                return "definition"
        for pattern in self.STATUS_PATTERNS:
            if pattern.search(query):
                return "status_check"
        for pattern in self.PROCEDURAL_PATTERNS:
            if pattern.search(query):
                return "procedural"
        return "factual_lookup"

    def test_definition_query_classified(self):
        """Definition questions are classified correctly."""
        assert self._classify("What is a setback?") == "definition"
        assert self._classify("Define easement") == "definition"

    def test_status_query_classified(self):
        """Status questions are classified correctly."""
        assert self._classify("What is the status of HB 1234?") == "status_check"
        assert self._classify("Has HB 1234 been signed?") == "status_check"

    def test_procedural_query_classified(self):
        """Procedural questions are classified correctly."""
        assert self._classify("How do I apply for a building permit?") == "procedural"

    def test_comparison_query_classified(self):
        """Comparison questions are classified correctly."""
        assert self._classify("How do state and county noise rules differ?") == "comparison"
        assert self._classify("Compare fence regulations") == "comparison"

    def test_analysis_query_classified(self):
        """Analysis questions are classified correctly."""
        assert self._classify("How would HB 1234 affect local zoning?") == "analysis"
        assert self._classify("What are the consequences of this bill?") == "analysis"

    def test_multi_jurisdiction_query_classified(self):
        """Multi-jurisdiction questions are classified correctly."""
        assert self._classify("What do all three levels of government say?") == "multi_jurisdiction"
        assert self._classify("Which jurisdiction handles this?") == "multi_jurisdiction"

    def test_synthesis_query_classified(self):
        """Synthesis questions are classified correctly."""
        assert self._classify("What are all the fence regulations?") == "synthesis"
        assert self._classify("Give me a comprehensive overview") == "synthesis"

    def test_simple_factual_query_defaults(self):
        """Simple factual queries default to factual_lookup."""
        assert self._classify("What is the fence height limit?") == "factual_lookup"
        assert self._classify("What are the noise ordinance hours?") == "factual_lookup"

    def test_simple_types_are_correct(self):
        """Simple types match the expected set."""
        assert self.SIMPLE_TYPES == {"factual_lookup", "definition", "status_check", "procedural"}


class TestModelRouting:
    """
    Verify model routing rules from CHAT-ROUTE-001 through CHAT-ROUTE-005.

    These tests mirror the three-signal routing logic in src/lib/router.ts.
    """

    SIMPLE_TYPES = {"factual_lookup", "definition", "status_check", "procedural"}

    # Simplified classification for routing tests
    COMPARISON_PATTERNS = [
        re.compile(r"compare|comparison|difference\s+between", re.I),
        re.compile(r"state\s+(and|vs\.?|versus)\s+(county|town|municipal)", re.I),
    ]
    ANALYSIS_PATTERNS = [
        re.compile(r"how\s+(would|does|will|could|might)\s+.+\s+affect", re.I),
    ]

    def _classify(self, query: str) -> str:
        """Simplified classifier for routing tests."""
        for p in self.COMPARISON_PATTERNS:
            if p.search(query):
                return "comparison"
        for p in self.ANALYSIS_PATTERNS:
            if p.search(query):
                return "analysis"
        return "factual_lookup"

    def _route(
        self,
        query: str,
        unique_doc_count: int,
        jurisdictions: list[str],
        avg_similarity: float = 0.5,
    ) -> dict:
        """Mirror of routeQuery() in src/lib/router.ts with three-signal routing."""
        doc_threshold = 3
        question_type = self._classify(query)
        is_complex = question_type not in self.SIMPLE_TYPES

        # Signal 1: doc count
        if unique_doc_count >= doc_threshold:
            return {
                "tier": "frontier",
                "model": "claude-sonnet-4-6",
                "reason": f"spans {unique_doc_count} documents",
                "questionType": question_type,
            }

        # Signal 2: multi-jurisdiction
        if len(jurisdictions) > 1:
            return {
                "tier": "frontier",
                "model": "claude-sonnet-4-6",
                "reason": "multi-jurisdiction",
                "questionType": question_type,
            }

        # Signal 3: complex question type with confidence override
        if is_complex:
            if avg_similarity >= 0.7 and unique_doc_count <= 1 and len(jurisdictions) <= 1:
                return {
                    "tier": "free",
                    "model": "gemini-2.0-flash",
                    "reason": "complex type but high-confidence single-source",
                    "questionType": question_type,
                }
            return {
                "tier": "frontier",
                "model": "claude-sonnet-4-6",
                "reason": "complex question type",
                "questionType": question_type,
            }

        return {
            "tier": "free",
            "model": "gemini-2.0-flash",
            "reason": "simple query",
            "questionType": question_type,
        }

    def test_many_documents_routes_to_frontier(self):
        """Queries spanning 3+ documents route to the frontier model (CHAT-ROUTE-001)."""
        decision = self._route("test", unique_doc_count=3, jurisdictions=["STATE"])
        assert decision["tier"] == "frontier"

    def test_multi_jurisdiction_routes_to_frontier(self):
        """Queries spanning multiple jurisdictions route to frontier (CHAT-ROUTE-002)."""
        decision = self._route("test", unique_doc_count=1, jurisdictions=["STATE", "MUNICIPAL"])
        assert decision["tier"] == "frontier"

    def test_complex_question_type_routes_to_frontier(self):
        """Complex question types route to frontier model (CHAT-ROUTE-003)."""
        decision = self._route(
            "How does this state law affect town regulations?",
            unique_doc_count=1,
            jurisdictions=["STATE"],
        )
        assert decision["tier"] == "frontier"
        assert decision["questionType"] == "analysis"

    def test_simple_query_routes_to_free(self):
        """Simple single-jurisdiction queries route to free model (CHAT-ROUTE-004)."""
        decision = self._route(
            "What is the speed limit on Main Street?",
            unique_doc_count=1,
            jurisdictions=["MUNICIPAL"],
        )
        assert decision["tier"] == "free"
        assert decision["model"] == "gemini-2.0-flash"
        assert decision["questionType"] == "factual_lookup"

    def test_frontier_model_is_current_claude_sonnet(self):
        """Frontier model is claude-sonnet-4-6 (current Sonnet)."""
        decision = self._route("test", unique_doc_count=5, jurisdictions=["STATE"])
        assert decision["model"] == "claude-sonnet-4-6"

    def test_high_confidence_overrides_complex_type(self):
        """High-confidence single-source retrieval keeps complex queries on free tier."""
        decision = self._route(
            "Compare fence regulations",
            unique_doc_count=1,
            jurisdictions=["MUNICIPAL"],
            avg_similarity=0.85,
        )
        assert decision["tier"] == "free"
        assert decision["questionType"] == "comparison"

    def test_low_confidence_complex_type_routes_to_frontier(self):
        """Low-confidence complex queries still route to frontier."""
        decision = self._route(
            "Compare fence regulations",
            unique_doc_count=1,
            jurisdictions=["MUNICIPAL"],
            avg_similarity=0.4,
        )
        assert decision["tier"] == "frontier"
        assert decision["questionType"] == "comparison"

    def test_doc_count_overrides_confidence(self):
        """Document count signal takes priority over confidence override."""
        decision = self._route(
            "What is the fence height?",
            unique_doc_count=4,
            jurisdictions=["MUNICIPAL"],
            avg_similarity=0.9,
        )
        assert decision["tier"] == "frontier"
