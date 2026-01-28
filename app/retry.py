"""
Safe retry infrastructure for agent swarm.
Enables: "Can every task be retried safely?"
- Exponential backoff with jitter
- Configurable retriable exceptions
- Idempotent-friendly (caller must ensure operations are safe to retry)
"""
import asyncio
import logging
import random
from typing import TypeVar, Callable, Awaitable, Optional, Tuple, Type
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default: retry on these exception types (transient failures)
DEFAULT_RETRIABLE: Tuple[Type[Exception], ...] = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,  # includes socket errors, connection reset
)

# aiohttp exceptions (optional - avoid hard dependency)
try:
    import aiohttp
    _extra = (
        getattr(aiohttp, "ClientError", Exception),
        getattr(aiohttp, "ServerDisconnectedError", Exception),
        getattr(aiohttp, "ClientConnectorError", Exception),
    )
    DEFAULT_RETRIABLE = DEFAULT_RETRIABLE + _extra
except ImportError:
    pass


def is_retriable_default(exc: BaseException) -> bool:
    """
    Return True if the exception is typically retriable (transient).
    """
    for cls in DEFAULT_RETRIABLE:
        if isinstance(exc, cls):
            return True
    # Also retry on 5xx-style messages if wrapped
    msg = str(exc).lower()
    if "503" in msg or "502" in msg or "504" in msg or "timeout" in msg:
        return True
    return False


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    backoff_base: float = 2.0,
    jitter: bool = True,
    retriable: Optional[Callable[[BaseException], bool]] = None,
    operation_name: str = "operation",
) -> T:
    """
    Execute an async call with exponential backoff retry.
    
    Args:
        fn: No-arg async callable (e.g. lambda: session.get(url))
        max_retries: Number of retries after initial attempt (total attempts = max_retries + 1)
        backoff_base: Base delay in seconds; delay = backoff_base ** attempt
        jitter: Add random jitter to delay to avoid thundering herd
        retriable: Predicate(exc) -> True if we should retry; default: timeout/connection/5xx
        operation_name: Label for logging
    
    Returns:
        Result of fn()
    
    Raises:
        Last exception if all retries exhausted
    """
    if retriable is None:
        retriable = is_retriable_default
    
    last_exc: Optional[BaseException] = None
    
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except BaseException as e:
            last_exc = e
            if attempt == max_retries or not retriable(e):
                logger.warning(
                    f"{operation_name}: attempt {attempt + 1}/{max_retries + 1} failed: {e}; "
                    f"{'exhausted retries' if attempt == max_retries else 'not retriable'}"
                )
                raise
            
            delay = backoff_base ** (attempt + 1)
            if jitter:
                delay = delay * (0.5 + random.random())
            delay = min(delay, 60.0)  # Cap at 60s
            
            logger.info(
                f"{operation_name}: attempt {attempt + 1} failed ({e}), retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
    
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{operation_name}: unexpected retry loop exit")


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 2.0,
    jitter: bool = True,
    retriable: Optional[Callable[[BaseException], bool]] = None,
    operation_name: Optional[str] = None,
):
    """
    Decorator that adds retry with exponential backoff to an async function.
    
    Usage:
        @with_retry(max_retries=3, operation_name="search_arxiv")
        async def search_arxiv(query: str, limit: int = 10):
            ...
    """
    def decorator(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        name = operation_name or f.__name__
        
        @wraps(f)
        async def wrapper(*args, **kwargs) -> T:
            async def run():
                return await f(*args, **kwargs)
            return await retry_async(
                run,
                max_retries=max_retries,
                backoff_base=backoff_base,
                jitter=jitter,
                retriable=retriable,
                operation_name=name,
            )
        return wrapper
    return decorator
