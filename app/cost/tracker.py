"""
Cost tracking middleware for LLM API calls.
Tracks costs per domain, queue, and day for budget enforcement.
"""
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

# Model pricing (per 1M tokens) - update as needed
MODEL_PRICING = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 0.250, "output": 1.000},
    "gpt-4-turbo": {"input": 2.500, "output": 10.000},
    "gpt-3.5-turbo": {"input": 0.500, "output": 1.500},
    # Anthropic
    "claude-3-haiku-20240307": {"input": 0.250, "output": 1.250},
    "claude-3-sonnet-20240229": {"input": 3.000, "output": 15.000},
    "claude-3-opus-20240229": {"input": 15.000, "output": 75.000},
    # Default fallback
    "default": {"input": 1.000, "output": 3.000},
}


@dataclass
class LLMCall:
    """Record of a single LLM API call with cost."""
    timestamp: datetime
    model: str
    provider: str  # "openai" or "anthropic"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    domain: Optional[str] = None
    queue: Optional[str] = None
    agent: Optional[str] = None
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class CostTracker:
    """
    Tracks LLM API costs per domain, queue, and day.
    Thread-safe for concurrent agent execution.
    """
    
    def __init__(self):
        self._lock = Lock()
        self._calls: List[LLMCall] = []
        # Indexed by (date, domain, queue) for fast lookups
        self._daily_costs: Dict[tuple, float] = {}  # (date, domain, queue) -> cost
        self._domain_costs: Dict[str, float] = {}  # domain -> total cost
        self._queue_costs: Dict[str, float] = {}  # queue -> total cost
    
    def record_call(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        agent: Optional[str] = None,
        duration_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> LLMCall:
        """
        Record an LLM API call and calculate cost.
        
        Returns:
            LLMCall record
        """
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        
        call = LLMCall(
            timestamp=datetime.utcnow(),
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            domain=domain,
            queue=queue,
            agent=agent,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        
        with self._lock:
            self._calls.append(call)
            
            # Update daily cost (by date, domain, queue)
            today = date.today()
            key = (today, domain or "global", queue or "default")
            self._daily_costs[key] = self._daily_costs.get(key, 0.0) + cost
            
            # Update domain cost
            if domain:
                self._domain_costs[domain] = self._domain_costs.get(domain, 0.0) + cost
            
            # Update queue cost
            if queue:
                self._queue_costs[queue] = self._queue_costs.get(queue, 0.0) + cost
        
        logger.debug(
            f"LLM call: {model} ({provider}) | "
            f"tokens: {input_tokens}+{output_tokens} | "
            f"cost: ${cost:.6f} | "
            f"domain: {domain or 'N/A'} | queue: {queue or 'N/A'}"
        )
        
        return call
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for a model call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def get_daily_cost(
        self,
        target_date: Optional[date] = None,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
    ) -> float:
        """
        Get total cost for a specific day, optionally filtered by domain/queue.
        
        Args:
            target_date: Date to check (default: today)
            domain: Filter by domain (None = all domains)
            queue: Filter by queue (None = all queues)
        
        Returns:
            Total cost in USD
        """
        if target_date is None:
            target_date = date.today()
        
        with self._lock:
            if domain is None and queue is None:
                # Sum all costs for this date
                return sum(
                    cost for (d, dom, q), cost in self._daily_costs.items()
                    if d == target_date
                )
            else:
                key = (target_date, domain or "global", queue or "default")
                return self._daily_costs.get(key, 0.0)
    
    def get_domain_cost(self, domain: str) -> float:
        """Get total cost for a domain (all time)."""
        with self._lock:
            return self._domain_costs.get(domain, 0.0)
    
    def get_queue_cost(self, queue: str) -> float:
        """Get total cost for a queue (all time)."""
        with self._lock:
            return self._queue_costs.get(queue, 0.0)
    
    def get_total_cost(self) -> float:
        """Get total cost across all domains/queues/days."""
        with self._lock:
            return sum(self._daily_costs.values())
    
    def get_recent_calls(self, limit: int = 100) -> List[LLMCall]:
        """Get most recent LLM calls."""
        with self._lock:
            return self._calls[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cost statistics summary."""
        with self._lock:
            total_calls = len(self._calls)
            successful_calls = sum(1 for c in self._calls if c.success)
            total_tokens = sum(c.input_tokens + c.output_tokens for c in self._calls)
            
            return {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": total_calls - successful_calls,
                "total_cost_usd": self.get_total_cost(),
                "total_tokens": total_tokens,
                "domains_with_costs": len(self._domain_costs),
                "queues_with_costs": len(self._queue_costs),
                "top_domains": sorted(
                    self._domain_costs.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10],
                "top_queues": sorted(
                    self._queue_costs.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10],
            }


# Global cost tracker instance
_cost_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    return _cost_tracker


def track_llm_call(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    agent: Optional[str] = None,
    duration_ms: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
) -> LLMCall:
    """
    Convenience function to record an LLM call.
    
    Usage:
        call = track_llm_call(
            model="gpt-4o-mini",
            provider="openai",
            input_tokens=500,
            output_tokens=200,
            domain="Algebra",
            agent="source_gatherer"
        )
    """
    return _cost_tracker.record_call(
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        domain=domain,
        queue=queue,
        agent=agent,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
