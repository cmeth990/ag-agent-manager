"""Unit tests for budget envelopes."""
import pytest
from app.cost.envelopes import BudgetEnvelope, EnvelopeManager, get_envelope_manager, BudgetExceededError


class TestBudgetEnvelope:
    """Tests for BudgetEnvelope."""

    def test_all_time_cap_allows_under(self):
        env = BudgetEnvelope("task:1", cap_usd=10.0, window="all_time")
        allowed, reason = env.check_cap(additional_cost=1.0)
        assert allowed is True
        assert reason is None

    def test_all_time_cap_denies_over(self):
        env = BudgetEnvelope("task:1", cap_usd=10.0, window="all_time")
        env.record_spend(9.0)
        allowed, reason = env.check_cap(additional_cost=2.0)
        assert allowed is False
        assert "exceeded" in (reason or "").lower()

    def test_per_call_cap_denies_large_call(self):
        env = BudgetEnvelope("tool", cap_usd=0.10, window="per_call")
        allowed, reason = env.check_cap(additional_cost=1.0)
        assert allowed is False
        assert reason is not None

    def test_per_call_cap_allows_small_call(self):
        env = BudgetEnvelope("tool", cap_usd=1.0, window="per_call")
        allowed, reason = env.check_cap(additional_cost=0.50)
        assert allowed is True

    def test_get_remaining_all_time(self):
        env = BudgetEnvelope("task:1", cap_usd=10.0, window="all_time")
        env.record_spend(3.0)
        assert env.get_remaining() == 7.0


class TestEnvelopeManager:
    """Tests for EnvelopeManager."""

    def test_set_and_get_envelope(self):
        mgr = EnvelopeManager()
        mgr.set_envelope("test_scope", cap_usd=5.0, window="all_time")
        env = mgr.get_envelope("test_scope")
        assert env is not None
        assert env.cap_usd == 5.0
        assert env.scope == "test_scope"

    def test_enforce_all_caps_raises_when_over(self):
        mgr = EnvelopeManager()
        mgr.set_envelope("per_tool_call", cap_usd=0.001, window="per_call")
        with pytest.raises(BudgetExceededError):
            mgr.enforce_all_caps(tool_name="test_tool", additional_cost=1.0)

    def test_enforce_all_caps_passes_when_under(self):
        mgr = EnvelopeManager()
        mgr.set_envelope("per_tool_call", cap_usd=10.0, window="per_call")
        mgr.enforce_all_caps(tool_name="test_tool", additional_cost=0.01)
        # No raise
