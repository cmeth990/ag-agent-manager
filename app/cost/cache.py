"""
Caching and memoization for cost reduction.
Caches: fetched docs, embeddings, source scores, extraction results.
"""
import logging
import hashlib
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


class CacheEntry:
    """A single cache entry with TTL."""
    
    def __init__(self, value: Any, ttl_seconds: int = 3600):
        self.value = value
        self.created_at = datetime.utcnow()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds


class CostCache:
    """
    In-memory cache for expensive operations.
    Can be extended to use Redis/Postgres for persistence.
    """
    
    def __init__(self):
        self._lock = Lock()
        # key -> CacheEntry
        self._cache: Dict[str, CacheEntry] = {}
        # Default TTLs (seconds)
        self._default_ttls = {
            "fetched_doc": 86400,  # 24 hours
            "cleaned_text": 86400,
            "embedding": 604800,  # 7 days
            "source_score": 3600,  # 1 hour
            "extraction_result": 86400,  # 24 hours
        }
    
    def _make_key(self, cache_type: str, *args, **kwargs) -> str:
        """Generate cache key from type and arguments."""
        # Hash args and kwargs
        key_parts = [cache_type]
        if args:
            key_parts.append(str(args))
        if kwargs:
            # Sort kwargs for consistent hashing
            sorted_kwargs = json.dumps(kwargs, sort_keys=True)
            key_parts.append(sorted_kwargs)
        
        key_str = "|".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(
        self,
        cache_type: str,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """
        Get cached value.
        
        Args:
            cache_type: Type of cache (e.g., "fetched_doc", "extraction_result")
            *args, **kwargs: Arguments used to generate cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        key = self._make_key(cache_type, *args, **kwargs)
        
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            logger.debug(f"Cache hit: {cache_type} (key: {key[:8]}...)")
            return entry.value
    
    def set(
        self,
        cache_type: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        *args,
        **kwargs,
    ) -> None:
        """
        Set cached value.
        
        Args:
            cache_type: Type of cache
            value: Value to cache
            ttl_seconds: TTL in seconds (None = use default for cache_type)
            *args, **kwargs: Arguments used to generate cache key
        """
        if ttl_seconds is None:
            ttl_seconds = self._default_ttls.get(cache_type, 3600)
        
        key = self._make_key(cache_type, *args, **kwargs)
        
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds=ttl_seconds)
            logger.debug(f"Cached: {cache_type} (key: {key[:8]}..., ttl: {ttl_seconds}s)")
    
    def invalidate(self, cache_type: Optional[str] = None) -> None:
        """Invalidate cache entries (all or by type)."""
        with self._lock:
            if cache_type:
                # Remove entries matching cache_type prefix
                keys_to_remove = [
                    k for k in self._cache.keys()
                    if k.startswith(self._make_key(cache_type, "").rsplit("|", 1)[0])
                ]
                for k in keys_to_remove:
                    del self._cache[k]
                logger.info(f"Invalidated {len(keys_to_remove)} entries for {cache_type}")
            else:
                self._cache.clear()
                logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e.is_expired())
            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": total - expired,
            }


# Global cache instance
_cache = CostCache()


def get_cache() -> CostCache:
    """Get the global cache instance."""
    return _cache


def cached(
    cache_type: str,
    ttl_seconds: Optional[int] = None,
    key_func: Optional[Callable] = None,
):
    """
    Decorator to cache function results.
    
    Args:
        cache_type: Type of cache
        ttl_seconds: TTL in seconds
        key_func: Optional function to generate cache key from args/kwargs
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
                cache_args = cache_key[0] if isinstance(cache_key, tuple) else ()
                cache_kwargs = cache_key[1] if isinstance(cache_key, tuple) and len(cache_key) > 1 else cache_key if isinstance(cache_key, dict) else {}
            else:
                cache_args = args
                cache_kwargs = kwargs
            
            # Check cache
            cached_value = _cache.get(cache_type, *cache_args, **cache_kwargs)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            _cache.set(cache_type, result, ttl_seconds=ttl_seconds, *cache_args, **cache_kwargs)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
                cache_args = cache_key[0] if isinstance(cache_key, tuple) else ()
                cache_kwargs = cache_key[1] if isinstance(cache_key, tuple) and len(cache_key) > 1 else cache_key if isinstance(cache_key, dict) else {}
            else:
                cache_args = args
                cache_kwargs = kwargs
            
            # Check cache
            cached_value = _cache.get(cache_type, *cache_args, **cache_kwargs)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result
            _cache.set(cache_type, result, ttl_seconds=ttl_seconds, *cache_args, **cache_kwargs)
            
            return result
        
        # Return appropriate wrapper
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
