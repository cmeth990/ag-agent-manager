"""Unit tests for rate limiter."""
import pytest
from app.queue.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_fresh_source_allowed(self):
        rl = RateLimiter()
        rl.set_limit("test_source", requests_per_minute=2, requests_per_hour=10)
        allowed, reason = rl.check_rate_limit("test_source")
        assert allowed is True
        assert reason is None

    def test_over_per_minute_denied(self):
        rl = RateLimiter()
        rl.set_limit("test_source", requests_per_minute=2, requests_per_hour=100)
        rl.record_request("test_source")
        rl.record_request("test_source")
        allowed, reason = rl.check_rate_limit("test_source")
        assert allowed is False
        assert "rate limit" in (reason or "").lower()

    def test_after_record_still_under_limit(self):
        rl = RateLimiter()
        rl.set_limit("test_source", requests_per_minute=5, requests_per_hour=100)
        rl.record_request("test_source")
        rl.record_request("test_source")
        allowed, reason = rl.check_rate_limit("test_source")
        assert allowed is True

    def test_default_limits_exist(self):
        rl = RateLimiter()
        allowed, _ = rl.check_rate_limit("unknown_source")
        assert allowed is True
