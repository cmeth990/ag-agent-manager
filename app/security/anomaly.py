"""
Anomaly detection: sudden surge of new concepts from one domain = suspicious.
Track ingestion rate per domain and flag anomalies.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# Default: flag if more than this many concepts from one domain in window
DEFAULT_SURGE_THRESHOLD = 50
DEFAULT_WINDOW_MINUTES = 60

# In-memory ingestion counters: (domain -> list of timestamps)
_ingestion_timestamps: Dict[str, list] = defaultdict(list)
_lock = Lock()


def record_ingestion(domain: str, count: int = 1) -> None:
    """Record that we ingested `count` concepts from `domain` (now)."""
    now = datetime.utcnow()
    with _lock:
        for _ in range(count):
            _ingestion_timestamps[domain].append(now)


def _trim_old(domain: str, window_minutes: int) -> None:
    """Remove timestamps outside the window."""
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    with _lock:
        _ingestion_timestamps[domain] = [
            t for t in _ingestion_timestamps[domain]
            if t >= cutoff
        ]


def check_ingestion_anomaly(
    domain: str,
    proposed_add_count: int,
    surge_threshold: int = DEFAULT_SURGE_THRESHOLD,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> Dict[str, Any]:
    """
    Check if adding `proposed_add_count` concepts from `domain` would be an anomaly.
    
    Anomaly = (recent ingestions in window + proposed_add_count) > surge_threshold.
    
    Returns:
        Dict with:
        - is_anomaly: bool
        - current_count: count in window for this domain
        - after_add: current_count + proposed_add_count
        - threshold: surge_threshold
        - message: optional warning message
    """
    _trim_old(domain, window_minutes)
    with _lock:
        current_count = len(_ingestion_timestamps[domain])
    
    after_add = current_count + proposed_add_count
    is_anomaly = after_add > surge_threshold
    
    result = {
        "is_anomaly": is_anomaly,
        "current_count": current_count,
        "after_add": after_add,
        "threshold": surge_threshold,
        "domain": domain,
        "window_minutes": window_minutes,
    }
    
    if is_anomaly:
        result["message"] = (
            f"Suspicious surge: domain '{domain}' would have {after_add} concepts "
            f"in {window_minutes} min (threshold {surge_threshold}). "
            f"Consider splitting or delaying ingestion."
        )
        logger.warning(result["message"])
    
    return result
