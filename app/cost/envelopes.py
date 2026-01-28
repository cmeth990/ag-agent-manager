"""
Budget envelopes: per-task, per-agent/day, per-queue concurrency, per-tool call caps.
Enables layered cost defenses.
"""
import logging
import os
from typing import Dict, Optional, Any
from datetime import date
from threading import Lock
from collections import defaultdict
from app.cost.tracker import get_cost_tracker
from app.cost.budget import BudgetExceededError

logger = logging.getLogger(__name__)


class BudgetEnvelope:
    """
    Budget envelope for a specific scope (task, agent, queue, tool).
    Tracks spending and enforces caps.
    """
    
    def __init__(
        self,
        scope: str,  # e.g., "task:123", "agent:source_gatherer", "queue:ingestion"
        cap_usd: float,
        window: str = "all_time",  # "all_time", "daily", "per_call"
    ):
        self.scope = scope
        self.cap_usd = cap_usd
        self.window = window
        self.spent_usd = 0.0
        self._lock = Lock()
        self._daily_spent: Dict[date, float] = defaultdict(float)
        self._call_count = 0
    
    def check_cap(self, additional_cost: float = 0.0) -> tuple[bool, Optional[str]]:
        """
        Check if spending additional_cost would exceed cap.
        
        Returns:
            (allowed, reason)
        """
        with self._lock:
            if self.window == "all_time":
                if self.spent_usd + additional_cost > self.cap_usd:
                    return (
                        False,
                        f"Budget envelope '{self.scope}' exceeded: ${self.spent_usd:.4f} + ${additional_cost:.4f} > ${self.cap_usd:.2f}"
                    )
            elif self.window == "daily":
                today = date.today()
                daily_spent = self._daily_spent[today]
                if daily_spent + additional_cost > self.cap_usd:
                    return (
                        False,
                        f"Daily budget envelope '{self.scope}' exceeded: ${daily_spent:.4f} + ${additional_cost:.4f} > ${self.cap_usd:.2f}"
                    )
            elif self.window == "per_call":
                if additional_cost > self.cap_usd:
                    return (
                        False,
                        f"Per-call budget envelope '{self.scope}' exceeded: ${additional_cost:.4f} > ${self.cap_usd:.2f}"
                    )
        
        return (True, None)
    
    def record_spend(self, cost_usd: float) -> None:
        """Record spending."""
        with self._lock:
            self.spent_usd += cost_usd
            if self.window == "daily":
                today = date.today()
                self._daily_spent[today] += cost_usd
            self._call_count += 1
    
    def get_remaining(self) -> float:
        """Get remaining budget."""
        with self._lock:
            if self.window == "all_time":
                return max(0.0, self.cap_usd - self.spent_usd)
            elif self.window == "daily":
                today = date.today()
                daily_spent = self._daily_spent[today]
                return max(0.0, self.cap_usd - daily_spent)
            else:  # per_call
                return self.cap_usd  # Always available for next call


class EnvelopeManager:
    """
    Manages budget envelopes for tasks, agents, queues, and tools.
    """
    
    def __init__(self):
        self._lock = Lock()
        self._envelopes: Dict[str, BudgetEnvelope] = {}
        self._load_from_env()
    
    def _load_from_env(self):
        """Load envelope caps from environment variables."""
        # Per-task cap
        per_task = os.getenv("COST_PER_TASK_CAP_USD")
        if per_task:
            try:
                self.set_envelope("per_task", float(per_task), window="all_time")
            except ValueError:
                logger.warning(f"Invalid COST_PER_TASK_CAP_USD: {per_task}")
        
        # Per-agent daily cap
        per_agent = os.getenv("COST_PER_AGENT_DAILY_CAP_USD")
        if per_agent:
            try:
                self.set_envelope("per_agent", float(per_agent), window="daily")
            except ValueError:
                logger.warning(f"Invalid COST_PER_AGENT_DAILY_CAP_USD: {per_agent}")
        
        # Per-queue concurrency cap (per concurrent task)
        per_queue = os.getenv("COST_PER_QUEUE_CONCURRENCY_CAP_USD")
        if per_queue:
            try:
                self.set_envelope("per_queue_concurrency", float(per_queue), window="per_call")
            except ValueError:
                logger.warning(f"Invalid COST_PER_QUEUE_CONCURRENCY_CAP_USD: {per_queue}")
        
        # Per-tool call cap
        per_tool = os.getenv("COST_PER_TOOL_CALL_CAP_USD")
        if per_tool:
            try:
                self.set_envelope("per_tool_call", float(per_tool), window="per_call")
            except ValueError:
                logger.warning(f"Invalid COST_PER_TOOL_CALL_CAP_USD: {per_tool}")
    
    def set_envelope(
        self,
        scope: str,
        cap_usd: float,
        window: str = "all_time",
    ) -> None:
        """Set or update a budget envelope."""
        with self._lock:
            self._envelopes[scope] = BudgetEnvelope(scope, cap_usd, window)
            logger.info(f"Set budget envelope '{scope}': ${cap_usd:.2f} ({window})")
    
    def get_envelope(self, scope: str) -> Optional[BudgetEnvelope]:
        """Get envelope for a scope."""
        with self._lock:
            return self._envelopes.get(scope)
    
    def check_task_cap(
        self,
        task_id: str,
        additional_cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """Check per-task cap."""
        envelope = self.get_envelope("per_task")
        if not envelope:
            return (True, None)
        
        task_scope = f"task:{task_id}"
        # Use per-task envelope template
        return envelope.check_cap(additional_cost)
    
    def check_agent_daily_cap(
        self,
        agent: str,
        additional_cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """Check per-agent daily cap."""
        envelope = self.get_envelope("per_agent")
        if not envelope:
            return (True, None)
        
        # Check agent-specific daily spending
        tracker = get_cost_tracker()
        today = date.today()
        agent_daily_cost = tracker.get_daily_cost(target_date=today, agent=agent)
        
        cap = envelope.cap_usd
        if agent_daily_cost + additional_cost > cap:
            return (
                False,
                f"Agent '{agent}' daily cap exceeded: ${agent_daily_cost:.4f} + ${additional_cost:.4f} > ${cap:.2f}"
            )
        
        return (True, None)
    
    def check_queue_concurrency_cap(
        self,
        queue: str,
        additional_cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """Check per-queue concurrency cap (per concurrent task)."""
        envelope = self.get_envelope("per_queue_concurrency")
        if not envelope:
            return (True, None)
        
        return envelope.check_cap(additional_cost)
    
    def check_tool_call_cap(
        self,
        tool_name: str,
        additional_cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """Check per-tool call cap."""
        envelope = self.get_envelope("per_tool_call")
        if not envelope:
            return (True, None)
        
        return envelope.check_cap(additional_cost)
    
    def enforce_all_caps(
        self,
        task_id: Optional[str] = None,
        agent: Optional[str] = None,
        queue: Optional[str] = None,
        tool_name: Optional[str] = None,
        additional_cost: float = 0.0,
    ) -> None:
        """
        Enforce all applicable caps.
        
        Raises:
            BudgetExceededError if any cap would be exceeded
        """
        # Check per-task
        if task_id:
            allowed, reason = self.check_task_cap(task_id, additional_cost)
            if not allowed:
                raise BudgetExceededError(reason)
        
        # Check per-agent daily
        if agent:
            allowed, reason = self.check_agent_daily_cap(agent, additional_cost)
            if not allowed:
                raise BudgetExceededError(reason)
        
        # Check per-queue concurrency
        if queue:
            allowed, reason = self.check_queue_concurrency_cap(queue, additional_cost)
            if not allowed:
                raise BudgetExceededError(reason)
        
        # Check per-tool call
        if tool_name:
            allowed, reason = self.check_tool_call_cap(tool_name, additional_cost)
            if not allowed:
                raise BudgetExceededError(reason)


# Global envelope manager
_envelope_manager = EnvelopeManager()


def get_envelope_manager() -> EnvelopeManager:
    """Get the global envelope manager."""
    return _envelope_manager
