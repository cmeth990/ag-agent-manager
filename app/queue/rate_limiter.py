"""
Rate limiting per domain/source.
Prevents overwhelming sources with too many requests.
"""
import logging
import time
from typing import Dict, Optional, Any
from collections import defaultdict
from threading import Lock
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default rate limits
DEFAULT_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "semantic_scholar": {"requests_per_minute": 100, "requests_per_hour": 5000},
    "arxiv": {"requests_per_minute": 10, "requests_per_hour": 200},
    "openalex": {"requests_per_minute": 50, "requests_per_hour": 10000},
    "wikipedia": {"requests_per_minute": 200, "requests_per_hour": 10000},
    "openstax": {"requests_per_minute": 20, "requests_per_hour": 1000},
    "khan_academy": {"requests_per_minute": 30, "requests_per_hour": 2000},
    "mit_ocw": {"requests_per_minute": 20, "requests_per_hour": 1000},
    "reddit": {"requests_per_minute": 60, "requests_per_hour": 1000},
    "default": {"requests_per_minute": 10, "requests_per_hour": 500},
}


class RateLimiter:
    """
    Rate limiter per domain/source.
    Tracks request timestamps and enforces limits.
    """
    
    def __init__(self):
        self._lock = Lock()
        # source -> list of request timestamps
        self._requests: Dict[str, list] = defaultdict(list)
        # domain -> list of request timestamps
        self._domain_requests: Dict[str, list] = defaultdict(list)
        # Rate limits per source
        self._limits: Dict[str, Dict[str, int]] = dict(DEFAULT_RATE_LIMITS)
    
    def set_limit(
        self,
        source: str,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
    ) -> None:
        """Set rate limit for a source."""
        with self._lock:
            if source not in self._limits:
                self._limits[source] = {}
            if requests_per_minute is not None:
                self._limits[source]["requests_per_minute"] = requests_per_minute
            if requests_per_hour is not None:
                self._limits[source]["requests_per_hour"] = requests_per_hour
    
    def _clean_old_requests(self, source: str, window_minutes: int = 60) -> None:
        """Remove request timestamps outside the window."""
        cutoff = time.monotonic() - (window_minutes * 60)
        with self._lock:
            self._requests[source] = [t for t in self._requests[source] if t > cutoff]
            for domain in list(self._domain_requests.keys()):
                self._domain_requests[domain] = [t for t in self._domain_requests[domain] if t > cutoff]
    
    def check_rate_limit(
        self,
        source: str,
        domain: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a request is allowed under rate limits.
        
        Returns:
            (allowed, reason) - allowed=True if within limits, reason=None if allowed,
            reason=error message if rate limited
        """
        self._clean_old_requests(source, window_minutes=60)
        
        limits = self._limits.get(source, self._limits["default"])
        now = time.monotonic()
        
        with self._lock:
            # Check per-minute limit
            minute_cutoff = now - 60
            recent_minute = [t for t in self._requests[source] if t > minute_cutoff]
            per_minute_limit = limits.get("requests_per_minute", 10)
            
            if len(recent_minute) >= per_minute_limit:
                return (
                    False,
                    f"Rate limit exceeded: {len(recent_minute)}/{per_minute_limit} requests per minute for {source}"
                )
            
            # Check per-hour limit
            hour_cutoff = now - 3600
            recent_hour = [t for t in self._requests[source] if t > hour_cutoff]
            per_hour_limit = limits.get("requests_per_hour", 500)
            
            if len(recent_hour) >= per_hour_limit:
                return (
                    False,
                    f"Rate limit exceeded: {len(recent_hour)}/{per_hour_limit} requests per hour for {source}"
                )
            
            # Check domain limit (if specified)
            if domain:
                domain_recent = [t for t in self._domain_requests[domain] if t > minute_cutoff]
                domain_per_minute = limits.get("domain_requests_per_minute", per_minute_limit // 2)
                if len(domain_recent) >= domain_per_minute:
                    return (
                        False,
                        f"Rate limit exceeded for domain '{domain}': {len(domain_recent)}/{domain_per_minute} requests per minute"
                    )
        
        return (True, None)
    
    def record_request(
        self,
        source: str,
        domain: Optional[str] = None,
    ) -> None:
        """Record a request (call after successful check_rate_limit)."""
        now = time.monotonic()
        with self._lock:
            self._requests[source].append(now)
            if domain:
                self._domain_requests[domain].append(now)
    
    def get_stats(self, source: str) -> Dict[str, Any]:
        """Get rate limit statistics for a source."""
        self._clean_old_requests(source)
        limits = self._limits.get(source, self._limits["default"])
        now = time.monotonic()
        
        with self._lock:
            minute_cutoff = now - 60
            hour_cutoff = now - 3600
            recent_minute = [t for t in self._requests[source] if t > minute_cutoff]
            recent_hour = [t for t in self._requests[source] if t > hour_cutoff]
        
        return {
            "source": source,
            "limits": limits,
            "requests_last_minute": len(recent_minute),
            "requests_last_hour": len(recent_hour),
            "remaining_minute": max(0, limits.get("requests_per_minute", 10) - len(recent_minute)),
            "remaining_hour": max(0, limits.get("requests_per_hour", 500) - len(recent_hour)),
        }


# Global rate limiter
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def check_rate_limit(source: str, domain: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Convenience: check rate limit for a source/domain."""
    return _rate_limiter.check_rate_limit(source, domain=domain)


def record_request(source: str, domain: Optional[str] = None) -> None:
    """Convenience: record a request."""
    _rate_limiter.record_request(source, domain=domain)
