"""
REDIS CACHING LAYER
===================

Centralized caching for all Resonant Genesis services.
Provides decorator-based caching, invalidation, and distributed locking.

Usage:
    from shared.cache.redis_cache import cache, get_cache
    
    @cache(ttl=300, prefix="user")
    async def get_user(user_id: str):
        return await db.get_user(user_id)
"""

import os
import json
import hashlib
import logging
import asyncio
from typing import Any, Optional, Callable, Union, TypeVar, List
from functools import wraps
from datetime import timedelta
import pickle

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RedisCache:
    """
    Redis-based caching with support for:
    - Key-value caching with TTL
    - JSON and pickle serialization
    - Cache invalidation patterns
    - Distributed locking
    - Connection pooling
    """
    
    def __init__(
        self,
        url: str = None,
        prefix: str = "rg",
        default_ttl: int = 300,
        max_connections: int = 50,
    ):
        self.url = url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self._client = None
        self._pool = None
    
    async def _get_client(self):
        """Get or create Redis client with connection pool."""
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._pool = redis.ConnectionPool.from_url(
                    self.url,
                    max_connections=self.max_connections,
                    decode_responses=False,
                )
                self._client = redis.Redis(connection_pool=self._pool)
                # Test connection
                await self._client.ping()
                logger.info(f"Redis connected: {self.url}")
            except ImportError:
                logger.error("redis package not installed. Run: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self._client = None
                raise
        return self._client
    
    def _make_key(self, key: str, prefix: str = None) -> str:
        """Create a namespaced cache key."""
        parts = [self.prefix]
        if prefix:
            parts.append(prefix)
        parts.append(key)
        return ":".join(parts)
    
    def _serialize(self, value: Any, use_pickle: bool = False) -> bytes:
        """Serialize value for storage."""
        if use_pickle:
            return pickle.dumps(value)
        try:
            return json.dumps(value).encode('utf-8')
        except (TypeError, ValueError):
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes, use_pickle: bool = False) -> Any:
        """Deserialize stored value."""
        if data is None:
            return None
        if use_pickle:
            return pickle.loads(data)
        try:
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return pickle.loads(data)
    
    async def get(
        self,
        key: str,
        prefix: str = None,
        default: Any = None,
    ) -> Any:
        """Get a cached value."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            data = await client.get(full_key)
            if data is None:
                return default
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        prefix: str = None,
        use_pickle: bool = False,
    ) -> bool:
        """Set a cached value."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            data = self._serialize(value, use_pickle)
            ttl = ttl or self.default_ttl
            await client.setex(full_key, ttl, data)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False
    
    async def delete(self, key: str, prefix: str = None) -> bool:
        """Delete a cached value."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            await client.delete(full_key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str, prefix: str = None) -> int:
        """Delete all keys matching a pattern."""
        try:
            client = await self._get_client()
            full_pattern = self._make_key(pattern, prefix)
            keys = []
            async for key in client.scan_iter(match=full_pattern):
                keys.append(key)
            if keys:
                await client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Cache delete_pattern failed for {pattern}: {e}")
            return 0
    
    async def exists(self, key: str, prefix: str = None) -> bool:
        """Check if a key exists."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            return await client.exists(full_key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for {key}: {e}")
            return False
    
    async def incr(self, key: str, prefix: str = None, amount: int = 1) -> int:
        """Increment a counter."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            return await client.incrby(full_key, amount)
        except Exception as e:
            logger.warning(f"Cache incr failed for {key}: {e}")
            return 0
    
    async def expire(self, key: str, ttl: int, prefix: str = None) -> bool:
        """Set expiration on a key."""
        try:
            client = await self._get_client()
            full_key = self._make_key(key, prefix)
            return await client.expire(full_key, ttl)
        except Exception as e:
            logger.warning(f"Cache expire failed for {key}: {e}")
            return False
    
    async def get_many(self, keys: List[str], prefix: str = None) -> dict:
        """Get multiple cached values."""
        try:
            client = await self._get_client()
            full_keys = [self._make_key(k, prefix) for k in keys]
            values = await client.mget(full_keys)
            return {
                keys[i]: self._deserialize(v) if v else None
                for i, v in enumerate(values)
            }
        except Exception as e:
            logger.warning(f"Cache get_many failed: {e}")
            return {k: None for k in keys}
    
    async def set_many(
        self,
        mapping: dict,
        ttl: int = None,
        prefix: str = None,
    ) -> bool:
        """Set multiple cached values."""
        try:
            client = await self._get_client()
            ttl = ttl or self.default_ttl
            pipe = client.pipeline()
            for key, value in mapping.items():
                full_key = self._make_key(key, prefix)
                data = self._serialize(value)
                pipe.setex(full_key, ttl, data)
            await pipe.execute()
            return True
        except Exception as e:
            logger.warning(f"Cache set_many failed: {e}")
            return False
    
    # ============== DISTRIBUTED LOCKING ==============
    
    async def acquire_lock(
        self,
        name: str,
        timeout: int = 10,
        blocking: bool = True,
        blocking_timeout: float = None,
    ) -> Optional[str]:
        """
        Acquire a distributed lock.
        Returns lock token if acquired, None otherwise.
        """
        try:
            client = await self._get_client()
            lock_key = self._make_key(name, "lock")
            token = hashlib.md5(f"{name}{asyncio.get_event_loop().time()}".encode()).hexdigest()
            
            if blocking:
                start = asyncio.get_event_loop().time()
                while True:
                    acquired = await client.set(lock_key, token, nx=True, ex=timeout)
                    if acquired:
                        return token
                    
                    if blocking_timeout and (asyncio.get_event_loop().time() - start) >= blocking_timeout:
                        return None
                    
                    await asyncio.sleep(0.1)
            else:
                acquired = await client.set(lock_key, token, nx=True, ex=timeout)
                return token if acquired else None
                
        except Exception as e:
            logger.warning(f"Lock acquire failed for {name}: {e}")
            return None
    
    async def release_lock(self, name: str, token: str) -> bool:
        """Release a distributed lock."""
        try:
            client = await self._get_client()
            lock_key = self._make_key(name, "lock")
            
            # Only release if we own the lock
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await client.eval(script, 1, lock_key, token)
            return result == 1
        except Exception as e:
            logger.warning(f"Lock release failed for {name}: {e}")
            return False
    
    # ============== RATE LIMITING ==============
    
    async def rate_limit(
        self,
        key: str,
        limit: int,
        window: int = 60,
    ) -> tuple[bool, int]:
        """
        Check rate limit using sliding window.
        Returns (allowed, remaining).
        """
        try:
            client = await self._get_client()
            full_key = self._make_key(key, "ratelimit")
            
            current = await client.incr(full_key)
            if current == 1:
                await client.expire(full_key, window)
            
            remaining = max(0, limit - current)
            allowed = current <= limit
            
            return allowed, remaining
        except Exception as e:
            logger.warning(f"Rate limit check failed for {key}: {e}")
            return True, limit  # Fail open
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            if self._pool:
                await self._pool.disconnect()
            self._client = None
            self._pool = None


# ============== GLOBAL INSTANCE ==============

_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


# ============== DECORATOR ==============

def cache(
    ttl: int = 300,
    prefix: str = None,
    key_builder: Callable = None,
    unless: Callable = None,
):
    """
    Decorator for caching function results.
    
    Usage:
        @cache(ttl=300, prefix="user")
        async def get_user(user_id: str):
            return await db.get_user(user_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Check unless condition
            if unless and unless(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key from function name and args
                key_parts = [func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            redis = get_cache()
            cached = await redis.get(cache_key, prefix=prefix)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await redis.set(cache_key, result, ttl=ttl, prefix=prefix)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(prefix: str, pattern: str = "*"):
    """
    Decorator to invalidate cache after function execution.
    
    Usage:
        @invalidate_cache(prefix="user", pattern="*")
        async def update_user(user_id: str, data: dict):
            return await db.update_user(user_id, data)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)
            
            # Invalidate matching cache entries
            redis = get_cache()
            await redis.delete_pattern(pattern, prefix=prefix)
            
            return result
        
        return wrapper
    return decorator
