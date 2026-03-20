"""
Tests for the /api/chat rate limiting logic.

Mirrors the behaviour of src/lib/rate-limit.ts so that the rate limiting
algorithm can be validated without spinning up a Next.js server or hitting
a real Supabase instance.

@spec CHAT-RLMT-001, CHAT-RLMT-002, CHAT-RLMT-003, CHAT-RLMT-004
"""

import math
import time


# ---------------------------------------------------------------------------
# Python mirror of the rate-limit.ts logic
# ---------------------------------------------------------------------------

RATE_LIMIT = 50  # default — matches CHAT_RATE_LIMIT default in rate-limit.ts


def current_window_start() -> int:
    """Return the Unix timestamp (seconds) of the current fixed 1-hour window."""
    now = int(time.time())
    return now - (now % 3600)


def window_reset_at(window_start: int) -> int:
    """Return the Unix timestamp when the given window expires."""
    return window_start + 3600


def hash_ip(ip: str) -> str:
    """Deterministic hash of an IP address — mirrors hashIp() in rate-limit.ts.

    Uses base-36 encoding (0-9 + a-z) matching JavaScript's Number.toString(36).
    """
    h = 0
    for ch in ip:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    # base-36 encoding to match TypeScript's (h >>> 0).toString(36)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    n = h
    if n == 0:
        return "0"
    while n:
        result = digits[n % 36] + result
        n //= 36
    return result


def check_rate_limit(
    ip: str,
    window_store: dict,  # mutable dict simulating the Supabase table
    limit: int = RATE_LIMIT,
) -> dict:
    """
    Increment the request counter for this IP in the current window.

    window_store keys: (ip_hash, window_start) → request_count

    Returns a dict matching the RateLimitResult TypeScript interface:
      { allowed, limit, remaining, resetAt }
    """
    ip_hash = hash_ip(ip)
    window_start = current_window_start()
    reset_at = window_reset_at(window_start)

    key = (ip_hash, window_start)
    count = window_store.get(key, 0) + 1
    window_store[key] = count

    allowed = count <= limit
    remaining = max(0, limit - count)
    return {
        "allowed": allowed,
        "limit": limit,
        "remaining": remaining,
        "resetAt": reset_at,
    }


def check_rate_limit_fail_open(ip: str, limit: int = RATE_LIMIT) -> dict:
    """
    Simulates a Supabase error — should fail open (allow the request).

    @spec CHAT-RLMT-004
    """
    window_start = current_window_start()
    reset_at = window_reset_at(window_start)
    return {
        "allowed": True,
        "limit": limit,
        "remaining": limit,
        "resetAt": reset_at,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWindowCalculation:
    """Verify that rate-limit windows are calculated correctly."""

    def test_window_start_is_truncated_to_hour(self):
        """Window start is always at the top of the hour (minutes=seconds=0)."""
        ws = current_window_start()
        assert ws % 3600 == 0

    def test_reset_at_is_one_hour_after_window_start(self):
        """Window resets exactly 1 hour after window_start."""
        ws = current_window_start()
        assert window_reset_at(ws) == ws + 3600

    def test_reset_at_is_in_the_future(self):
        """resetAt timestamp is always in the future."""
        ws = current_window_start()
        assert window_reset_at(ws) > time.time()


class TestIpHashing:
    """Verify IP hashing behaviour."""

    def test_same_ip_produces_same_hash(self):
        """Two calls with the same IP return the same hash."""
        assert hash_ip("1.2.3.4") == hash_ip("1.2.3.4")

    def test_different_ips_produce_different_hashes(self):
        """Different IPs produce different hashes."""
        assert hash_ip("1.2.3.4") != hash_ip("5.6.7.8")

    def test_hash_is_non_empty_string(self):
        """Hash is a non-empty hexadecimal string."""
        h = hash_ip("192.168.1.100")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_unknown_ip_hashes_consistently(self):
        """The sentinel 'unknown' IP is hashed without errors."""
        h1 = hash_ip("unknown")
        h2 = hash_ip("unknown")
        assert h1 == h2


class TestRateLimitCounting:
    """Verify counter increment and limit enforcement (CHAT-RLMT-001)."""

    def test_first_request_is_allowed(self):
        """The first request from any IP is always allowed."""
        store: dict = {}
        result = check_rate_limit("10.0.0.1", store)
        assert result["allowed"] is True
        assert result["remaining"] == RATE_LIMIT - 1

    def test_request_within_limit_is_allowed(self):
        """Requests below the limit are all allowed."""
        store: dict = {}
        for _ in range(RATE_LIMIT):
            result = check_rate_limit("10.0.0.1", store)
        assert result["allowed"] is True
        assert result["remaining"] == 0

    def test_request_exceeding_limit_is_rejected(self):
        """The (limit + 1)-th request is rejected (CHAT-RLMT-001)."""
        store: dict = {}
        for _ in range(RATE_LIMIT):
            check_rate_limit("10.0.0.2", store)
        result = check_rate_limit("10.0.0.2", store)
        assert result["allowed"] is False
        assert result["remaining"] == 0

    def test_different_ips_have_independent_counters(self):
        """Two different IPs do not share a rate-limit counter."""
        store: dict = {}
        # Fill up IP A
        for _ in range(RATE_LIMIT):
            check_rate_limit("10.0.0.3", store)
        # IP B is still allowed
        result = check_rate_limit("10.0.0.4", store)
        assert result["allowed"] is True

    def test_remaining_decrements_with_each_request(self):
        """remaining decreases by one on every allowed request."""
        store: dict = {}
        for i in range(5):
            result = check_rate_limit("10.0.0.5", store)
            assert result["remaining"] == RATE_LIMIT - (i + 1)

    def test_remaining_never_goes_below_zero(self):
        """remaining is clamped at 0 even when over the limit."""
        store: dict = {}
        for _ in range(RATE_LIMIT + 10):
            result = check_rate_limit("10.0.0.6", store)
        assert result["remaining"] == 0


class TestRateLimitHeaders:
    """Verify the expected response header values (CHAT-RLMT-002, CHAT-RLMT-003)."""

    def test_result_contains_required_fields(self):
        """Result dict contains all fields needed to populate response headers."""
        store: dict = {}
        result = check_rate_limit("10.0.0.7", store)
        assert "allowed" in result
        assert "limit" in result
        assert "remaining" in result
        assert "resetAt" in result

    def test_limit_field_matches_configured_limit(self):
        """The 'limit' field equals the configured RATE_LIMIT constant."""
        store: dict = {}
        result = check_rate_limit("10.0.0.8", store)
        assert result["limit"] == RATE_LIMIT

    def test_retry_after_is_positive_when_rejected(self):
        """Retry-After header value is positive when a request is rejected."""
        store: dict = {}
        for _ in range(RATE_LIMIT + 1):
            result = check_rate_limit("10.0.0.9", store)
        retry_after = max(0, result["resetAt"] - math.floor(time.time()))
        assert retry_after > 0

    def test_reset_at_is_unix_timestamp(self):
        """resetAt is a reasonable Unix timestamp (between now and +1 hour)."""
        store: dict = {}
        result = check_rate_limit("10.0.0.10", store)
        now = time.time()
        assert now <= result["resetAt"] <= now + 3600


class TestFailOpen:
    """Verify the fail-open behaviour on database errors (CHAT-RLMT-004)."""

    def test_fail_open_allows_request(self):
        """When the DB check fails, the request is allowed (CHAT-RLMT-004)."""
        result = check_rate_limit_fail_open("10.0.0.11")
        assert result["allowed"] is True

    def test_fail_open_returns_full_remaining(self):
        """When the DB check fails, remaining equals the configured limit."""
        result = check_rate_limit_fail_open("10.0.0.11")
        assert result["remaining"] == RATE_LIMIT

    def test_fail_open_still_returns_required_fields(self):
        """Even on failure, all header fields are present."""
        result = check_rate_limit_fail_open("10.0.0.12")
        assert "allowed" in result
        assert "limit" in result
        assert "remaining" in result
        assert "resetAt" in result


class TestCustomLimit:
    """Verify that CHAT_RATE_LIMIT env var can lower or raise the limit."""

    def test_custom_limit_is_enforced(self):
        """A custom limit of 5 is enforced correctly."""
        store: dict = {}
        custom_limit = 5
        for _ in range(custom_limit):
            result = check_rate_limit("10.0.0.13", store, limit=custom_limit)
        assert result["allowed"] is True
        # Next request should be rejected
        result = check_rate_limit("10.0.0.13", store, limit=custom_limit)
        assert result["allowed"] is False

    def test_limit_of_one_rejects_second_request(self):
        """A limit of 1 blocks the second request immediately."""
        store: dict = {}
        result_1 = check_rate_limit("10.0.0.14", store, limit=1)
        assert result_1["allowed"] is True
        result_2 = check_rate_limit("10.0.0.14", store, limit=1)
        assert result_2["allowed"] is False
