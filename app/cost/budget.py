"""
Budget management and enforcement for cost caps.
Enables: "Can you cap spend per domain/queue/day?"
"""
import logging
import os
from typing import Dict, Optional, Any
from datetime import date
from threading import Lock
from app.cost.tracker import get_cost_tracker

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when a budget cap is exceeded."""
    pass


class BudgetManager:
    """
    Manages budget caps per domain, queue, and day.
    Enforces hard caps that stop execution when exceeded.
    """
    
    def __init__(self):
        self._lock = Lock()
        # Budget limits: (date, domain, queue) -> limit_usd
        self._daily_limits: Dict[tuple, float] = {}
        # Domain limits: domain -> limit_usd (all time)
        self._domain_limits: Dict[str, float] = {}
        # Queue limits: queue -> limit_usd (all time)
        self._queue_limits: Dict[str, float] = {}
        # Global daily limit
        self._global_daily_limit: Optional[float] = None
        
        # Load from environment variables
        self._load_from_env()
    
    def _load_from_env(self):
        """Load budget limits from environment variables."""
        # Global daily limit
        global_limit = os.getenv("LLM_DAILY_BUDGET_USD")
        if global_limit:
            try:
                self._global_daily_limit = float(global_limit)
                logger.info(f"Global daily budget: ${self._global_daily_limit:.2f}")
            except ValueError:
                logger.warning(f"Invalid LLM_DAILY_BUDGET_USD: {global_limit}")
        
        # Domain-specific limits (format: DOMAIN_BUDGET_<DOMAIN>=<amount>)
        # Example: DOMAIN_BUDGET_Algebra=1.00
        for key, value in os.environ.items():
            if key.startswith("DOMAIN_BUDGET_"):
                domain = key.replace("DOMAIN_BUDGET_", "").replace("_", " ")
                try:
                    limit = float(value)
                    self.set_domain_limit(domain, limit)
                    logger.info(f"Domain budget for '{domain}': ${limit:.2f}")
                except ValueError:
                    logger.warning(f"Invalid budget for {key}: {value}")
    
    def set_daily_limit(
        self,
        limit_usd: float,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        target_date: Optional[date] = None,
    ):
        """
        Set a daily budget limit.
        
        Args:
            limit_usd: Maximum spend in USD
            domain: Apply to specific domain (None = global)
            queue: Apply to specific queue (None = all queues)
            target_date: Date to apply limit (None = today)
        """
        if target_date is None:
            target_date = date.today()
        
        with self._lock:
            key = (target_date, domain or "global", queue or "default")
            self._daily_limits[key] = limit_usd
            logger.info(
                f"Set daily limit: ${limit_usd:.2f} for "
                f"date={target_date}, domain={domain or 'all'}, queue={queue or 'all'}"
            )
    
    def set_domain_limit(self, domain: str, limit_usd: float):
        """Set a budget limit for a domain (all time)."""
        with self._lock:
            self._domain_limits[domain] = limit_usd
            logger.info(f"Set domain limit for '{domain}': ${limit_usd:.2f}")
    
    def set_queue_limit(self, queue: str, limit_usd: float):
        """Set a budget limit for a queue (all time)."""
        with self._lock:
            self._queue_limits[queue] = limit_usd
            logger.info(f"Set queue limit for '{queue}': ${limit_usd:.2f}")
    
    def set_global_daily_limit(self, limit_usd: float):
        """Set global daily budget limit."""
        with self._lock:
            self._global_daily_limit = limit_usd
            logger.info(f"Set global daily limit: ${limit_usd:.2f}")
    
    def check_budget(
        self,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        additional_cost: float = 0.0,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if budget allows spending additional_cost.
        
        Returns:
            (allowed, reason) - allowed=True if within budget, reason=None if allowed,
            reason=error message if not allowed
        """
        tracker = get_cost_tracker()
        today = date.today()
        
        with self._lock:
            # Check global daily limit
            if self._global_daily_limit is not None:
                global_daily_cost = tracker.get_daily_cost(target_date=today)
                if global_daily_cost + additional_cost > self._global_daily_limit:
                    return (
                        False,
                        f"Global daily budget exceeded: ${global_daily_cost:.4f} + ${additional_cost:.4f} > ${self._global_daily_limit:.2f}"
                    )
            
            # Check domain-specific daily limit
            if domain:
                key = (today, domain, queue or "default")
                if key in self._daily_limits:
                    limit = self._daily_limits[key]
                    current_cost = tracker.get_daily_cost(target_date=today, domain=domain, queue=queue)
                    if current_cost + additional_cost > limit:
                        return (
                            False,
                            f"Daily budget for domain '{domain}' exceeded: ${current_cost:.4f} + ${additional_cost:.4f} > ${limit:.2f}"
                        )
            
            # Check domain limit (all time)
            if domain and domain in self._domain_limits:
                limit = self._domain_limits[domain]
                current_cost = tracker.get_domain_cost(domain)
                if current_cost + additional_cost > limit:
                    return (
                        False,
                        f"Domain budget for '{domain}' exceeded: ${current_cost:.4f} + ${additional_cost:.4f} > ${limit:.2f}"
                    )
            
            # Check queue limit (all time)
            if queue and queue in self._queue_limits:
                limit = self._queue_limits[queue]
                current_cost = tracker.get_queue_cost(queue)
                if current_cost + additional_cost > limit:
                    return (
                        False,
                        f"Queue budget for '{queue}' exceeded: ${current_cost:.4f} + ${additional_cost:.4f} > ${limit:.2f}"
                    )
        
        return (True, None)
    
    def enforce_budget(
        self,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        additional_cost: float = 0.0,
    ):
        """
        Enforce budget - raises BudgetExceededError if cap would be exceeded.
        
        Raises:
            BudgetExceededError if budget would be exceeded
        """
        allowed, reason = self.check_budget(domain=domain, queue=queue, additional_cost=additional_cost)
        if not allowed:
            logger.warning(f"Budget exceeded: {reason}")
            raise BudgetExceededError(reason)
    
    def get_remaining_budget(
        self,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        target_date: Optional[date] = None,
    ) -> Optional[float]:
        """
        Get remaining budget for domain/queue/day.
        
        Returns:
            Remaining budget in USD, or None if no limit set
        """
        if target_date is None:
            target_date = date.today()
        
        tracker = get_cost_tracker()
        
        with self._lock:
            # Check global daily limit
            if self._global_daily_limit is not None:
                current = tracker.get_daily_cost(target_date=target_date)
                return max(0.0, self._global_daily_limit - current)
            
            # Check domain-specific daily limit
            if domain:
                key = (target_date, domain, queue or "default")
                if key in self._daily_limits:
                    limit = self._daily_limits[key]
                    current = tracker.get_daily_cost(target_date=target_date, domain=domain, queue=queue)
                    return max(0.0, limit - current)
            
            # Check domain limit (all time)
            if domain and domain in self._domain_limits:
                limit = self._domain_limits[domain]
                current = tracker.get_domain_cost(domain)
                return max(0.0, limit - current)
            
            # Check queue limit (all time)
            if queue and queue in self._queue_limits:
                limit = self._queue_limits[queue]
                current = tracker.get_queue_cost(queue)
                return max(0.0, limit - current)
        
        return None  # No limit set
    
    def get_status(self) -> Dict[str, Any]:
        """Get budget status summary."""
        tracker = get_cost_tracker()
        today = date.today()
        
        with self._lock:
            global_daily_cost = tracker.get_daily_cost(target_date=today)
            
            status = {
                "global_daily_limit": self._global_daily_limit,
                "global_daily_spent": global_daily_cost,
                "global_daily_remaining": (
                    max(0.0, self._global_daily_limit - global_daily_cost)
                    if self._global_daily_limit else None
                ),
                "domain_limits": dict(self._domain_limits),
                "queue_limits": dict(self._queue_limits),
                "daily_limits": {
                    f"{d}_{dom}_{q}": limit
                    for (d, dom, q), limit in self._daily_limits.items()
                },
            }
        
        return status


# Global budget manager instance
_budget_manager = BudgetManager()


def get_budget_manager() -> BudgetManager:
    """Get the global budget manager instance."""
    return _budget_manager
