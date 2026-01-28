"""
Circuit breaker for domains and sources.
Enables: "Can you pause a misbehaving domain/source quickly?"
"""
import logging
import time
from typing import Dict, Any, Optional, Set
from threading import Lock

logger = logging.getLogger(__name__)

# Default: open circuit after 5 failures in 60s; allow retry after 30s
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_RECOVERY_SECONDS = 30


class CircuitState:
    """State for a single circuit (domain or source)."""
    CLOSED = "closed"   # Normal operation
    OPEN = "open"       # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery

    def __init__(
        self,
        key: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        recovery_seconds: float = DEFAULT_RECOVERY_SECONDS,
    ):
        self.key = key
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds
        self.state = self.CLOSED
        self.failures: list = []  # timestamps of recent failures
        self.last_failure_at: Optional[float] = None
        self.opened_at: Optional[float] = None  # when circuit was opened
        self._lock = Lock()

    def record_success(self) -> None:
        with self._lock:
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                self.failures.clear()
                logger.info(f"Circuit {self.key}: half_open -> closed (recovery success)")
            elif self.state == self.CLOSED:
                # Optionally clear old failures on success
                now = time.monotonic()
                self.failures = [t for t in self.failures if now - t < self.window_seconds]

    def record_failure(self) -> None:
        now = time.monotonic()
        with self._lock:
            self.last_failure_at = now
            self.failures.append(now)
            # Drop failures outside window
            self.failures = [t for t in self.failures if now - t < self.window_seconds]

            if self.state == self.HALF_OPEN:
                self.state = self.OPEN
                self.opened_at = now
                logger.warning(f"Circuit {self.key}: half_open -> open (recovery failed)")
                return

            if self.state == self.CLOSED and len(self.failures) >= self.failure_threshold:
                self.state = self.OPEN
                self.opened_at = now
                logger.warning(
                    f"Circuit {self.key}: closed -> open "
                    f"(failures={len(self.failures)} in {self.window_seconds}s)"
                )

    def allow_request(self) -> bool:
        """Return True if a request is allowed (circuit closed or half-open)."""
        now = time.monotonic()
        with self._lock:
            if self.state == self.CLOSED:
                return True
            if self.state == self.OPEN:
                if self.opened_at is not None and (now - self.opened_at) >= self.recovery_seconds:
                    self.state = self.HALF_OPEN
                    self.opened_at = None
                    logger.info(f"Circuit {self.key}: open -> half_open (retry)")
                    return True
                return False
            # HALF_OPEN: allow one request to test
            return True

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "key": self.key,
                "state": self.state,
                "failure_count": len(self.failures),
                "last_failure_at": self.last_failure_at,
                "opened_at": self.opened_at,
            }

    def force_open(self) -> None:
        with self._lock:
            self.state = self.OPEN
            self.opened_at = time.monotonic()
            logger.info(f"Circuit {self.key}: forced open")

    def force_close(self) -> None:
        with self._lock:
            self.state = self.CLOSED
            self.failures.clear()
            self.opened_at = None
            logger.info(f"Circuit {self.key}: forced closed")


class CircuitBreakerRegistry:
    """Registry of circuit breakers per domain and per source."""
    _lock = Lock()
    _by_domain: Dict[str, CircuitState] = {}
    _by_source: Dict[str, CircuitState] = {}

    @classmethod
    def get_domain_circuit(cls, domain: str, **kwargs: Any) -> CircuitState:
        with cls._lock:
            if domain not in cls._by_domain:
                cls._by_domain[domain] = CircuitState(f"domain:{domain}", **kwargs)
            return cls._by_domain[domain]

    @classmethod
    def get_source_circuit(cls, source: str, **kwargs: Any) -> CircuitState:
        with cls._lock:
            if source not in cls._by_source:
                cls._by_source[source] = CircuitState(f"source:{source}", **kwargs)
            return cls._by_source[source]

    @classmethod
    def allow_domain(cls, domain: str) -> bool:
        return cls.get_domain_circuit(domain).allow_request()

    @classmethod
    def allow_source(cls, source: str) -> bool:
        return cls.get_source_circuit(source).allow_request()

    @classmethod
    def record_domain_success(cls, domain: str) -> None:
        cls.get_domain_circuit(domain).record_success()

    @classmethod
    def record_domain_failure(cls, domain: str) -> None:
        cls.get_domain_circuit(domain).record_failure()

    @classmethod
    def record_source_success(cls, source: str) -> None:
        cls.get_source_circuit(source).record_success()

    @classmethod
    def record_source_failure(cls, source: str) -> None:
        cls.get_source_circuit(source).record_failure()

    @classmethod
    def pause_domain(cls, domain: str) -> None:
        """Kill switch: open circuit for domain (pause)."""
        cls.get_domain_circuit(domain).force_open()

    @classmethod
    def pause_source(cls, source: str) -> None:
        """Kill switch: open circuit for source (pause)."""
        cls.get_source_circuit(source).force_open()

    @classmethod
    def resume_domain(cls, domain: str) -> None:
        cls.get_domain_circuit(domain).force_close()

    @classmethod
    def resume_source(cls, source: str) -> None:
        cls.get_source_circuit(source).force_close()

    @classmethod
    def list_status(cls) -> Dict[str, Any]:
        with cls._lock:
            return {
                "domains": {k: v.get_status() for k, v in cls._by_domain.items()},
                "sources": {k: v.get_status() for k, v in cls._by_source.items()},
            }


def check_domain_allowed(domain: str) -> bool:
    """Use before running domain-specific work. Returns False if domain is paused."""
    return CircuitBreakerRegistry.allow_domain(domain)


def check_source_allowed(source: str) -> bool:
    """Use before calling a source (e.g. semantic_scholar, arxiv). Returns False if source is paused."""
    return CircuitBreakerRegistry.allow_source(source)


def record_source_success(source: str) -> None:
    """Call after a source request succeeds."""
    CircuitBreakerRegistry.record_source_success(source)


def record_source_failure(source: str) -> None:
    """Call after a source request fails."""
    CircuitBreakerRegistry.record_source_failure(source)
