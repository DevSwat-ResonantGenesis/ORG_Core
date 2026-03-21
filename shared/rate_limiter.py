"""
Per-User Rate Limiting Service
===============================

Provides rate limiting functionality for the ResonantGenesis platform.
Supports:
- Per-user rate limits based on subscription tier
- Sliding window rate limiting
- Redis-backed distributed rate limiting
- Fallback to in-memory rate limiting

Author: Resonant Genesis Team
Date: December 29, 2025
"""

import os
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - using in-memory rate limiting")


class UserTier(Enum):
    """User subscription tiers with different rate limits."""
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tier."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_limit: int  # Max requests in 10 seconds
    
    # Feature-specific limits
    chat_messages_per_minute: int
    memory_operations_per_minute: int
    agent_executions_per_hour: int


# Default rate limits by tier
TIER_LIMITS: Dict[UserTier, RateLimitConfig] = {
    UserTier.FREE: RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=200,
        requests_per_day=1000,
        burst_limit=10,
        chat_messages_per_minute=10,
        memory_operations_per_minute=30,
        agent_executions_per_hour=10,
    ),
    UserTier.PLUS: RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        burst_limit=30,
        chat_messages_per_minute=30,
        memory_operations_per_minute=100,
        agent_executions_per_hour=50,
    ),
    UserTier.PRO: RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=5000,
        requests_per_day=50000,
        burst_limit=60,
        chat_messages_per_minute=60,
        memory_operations_per_minute=300,
        agent_executions_per_hour=200,
    ),
    UserTier.ENTERPRISE: RateLimitConfig(
        requests_per_minute=500,
        requests_per_hour=20000,
        requests_per_day=200000,
        burst_limit=200,
        chat_messages_per_minute=200,
        memory_operations_per_minute=1000,
        agent_executions_per_hour=1000,
    ),
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: float  # Unix timestamp
    limit: int
    retry_after: Optional[int] = None  # Seconds until retry allowed
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers for response."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window."""
    
    def __init__(self):
        # Structure: {user_id: {window_key: [(timestamp, count), ...]}}
        self._windows: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(
        self,
        user_id: str,
        action: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check if request is within rate limit."""
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            key = f"{action}:{window_seconds}"
            
            # Get user's request history for this window
            user_windows = self._windows[user_id]
            requests = user_windows[key]
            
            # Remove expired entries
            requests = [(ts, count) for ts, count in requests if ts > window_start]
            user_windows[key] = requests
            
            # Count requests in window
            current_count = sum(count for _, count in requests)
            
            if current_count >= limit:
                # Rate limited
                oldest = requests[0][0] if requests else now
                reset_at = oldest + window_seconds
                retry_after = int(reset_at - now) + 1
                
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    limit=limit,
                    retry_after=retry_after,
                )
            
            # Allow request and record it
            requests.append((now, 1))
            user_windows[key] = requests
            
            return RateLimitResult(
                allowed=True,
                remaining=limit - current_count - 1,
                reset_at=now + window_seconds,
                limit=limit,
            )
    
    async def get_usage(self, user_id: str, action: str, window_seconds: int) -> int:
        """Get current usage count for a user."""
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            key = f"{action}:{window_seconds}"
            
            requests = self._windows[user_id][key]
            requests = [(ts, count) for ts, count in requests if ts > window_start]
            
            return sum(count for _, count in requests)


class RedisRateLimiter:
    """Redis-backed distributed rate limiter."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client
    
    async def check_rate_limit(
        self,
        user_id: str,
        action: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check if request is within rate limit using Redis."""
        try:
            client = await self._get_client()
            now = time.time()
            key = f"ratelimit:{user_id}:{action}:{window_seconds}"
            
            # Use Redis sorted set for sliding window
            pipe = client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            
            # Count current entries
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry on key
            pipe.expire(key, window_seconds + 1)
            
            results = await pipe.execute()
            current_count = results[1]
            
            if current_count >= limit:
                # Get oldest entry for reset time
                oldest = await client.zrange(key, 0, 0, withscores=True)
                reset_at = oldest[0][1] + window_seconds if oldest else now + window_seconds
                retry_after = int(reset_at - now) + 1
                
                # Remove the request we just added since it's rate limited
                await client.zrem(key, str(now))
                
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    limit=limit,
                    retry_after=retry_after,
                )
            
            return RateLimitResult(
                allowed=True,
                remaining=limit - current_count - 1,
                reset_at=now + window_seconds,
                limit=limit,
            )
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open - allow request if Redis is down
            return RateLimitResult(
                allowed=True,
                remaining=limit,
                reset_at=time.time() + window_seconds,
                limit=limit,
            )
    
    async def get_usage(self, user_id: str, action: str, window_seconds: int) -> int:
        """Get current usage count for a user."""
        try:
            client = await self._get_client()
            now = time.time()
            key = f"ratelimit:{user_id}:{action}:{window_seconds}"
            
            # Remove expired and count
            await client.zremrangebyscore(key, 0, now - window_seconds)
            return await client.zcard(key)
        except Exception as e:
            logger.error(f"Redis get usage error: {e}")
            return 0


class RateLimiter:
    """
    Main rate limiter service.
    
    Uses Redis if available, falls back to in-memory.
    """
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        
        if REDIS_AVAILABLE and redis_url:
            self._backend = RedisRateLimiter(redis_url)
            self._backend_type = "redis"
            logger.info(f"Rate limiter using Redis: {redis_url}")
        else:
            self._backend = InMemoryRateLimiter()
            self._backend_type = "memory"
            logger.info("Rate limiter using in-memory storage")
    
    def get_tier_config(self, tier: UserTier) -> RateLimitConfig:
        """Get rate limit config for a tier."""
        return TIER_LIMITS.get(tier, TIER_LIMITS[UserTier.FREE])
    
    async def check_request(
        self,
        user_id: str,
        tier: UserTier = UserTier.FREE,
        action: str = "request",
    ) -> RateLimitResult:
        """
        Check if a request is allowed for a user.
        
        Args:
            user_id: User identifier
            tier: User's subscription tier
            action: Type of action (request, chat, memory, agent)
            
        Returns:
            RateLimitResult with allowed status and headers
        """
        config = self.get_tier_config(tier)
        
        # Determine limit based on action
        if action == "chat":
            limit = config.chat_messages_per_minute
            window = 60
        elif action == "memory":
            limit = config.memory_operations_per_minute
            window = 60
        elif action == "agent":
            limit = config.agent_executions_per_hour
            window = 3600
        elif action == "burst":
            limit = config.burst_limit
            window = 10
        else:
            # Default: per-minute limit
            limit = config.requests_per_minute
            window = 60
        
        result = await self._backend.check_rate_limit(
            user_id=user_id,
            action=action,
            limit=limit,
            window_seconds=window,
        )
        
        if not result.allowed:
            logger.warning(
                f"Rate limit exceeded: user={user_id}, tier={tier.value}, "
                f"action={action}, retry_after={result.retry_after}s"
            )
        
        return result
    
    async def check_multiple(
        self,
        user_id: str,
        tier: UserTier = UserTier.FREE,
        actions: list = None,
    ) -> Tuple[bool, Dict[str, RateLimitResult]]:
        """
        Check multiple rate limits at once.
        
        Returns:
            Tuple of (all_allowed, {action: result})
        """
        if actions is None:
            actions = ["request", "burst"]
        
        results = {}
        all_allowed = True
        
        for action in actions:
            result = await self.check_request(user_id, tier, action)
            results[action] = result
            if not result.allowed:
                all_allowed = False
        
        return all_allowed, results
    
    async def get_user_usage(self, user_id: str, tier: UserTier = UserTier.FREE) -> Dict:
        """Get current usage stats for a user."""
        config = self.get_tier_config(tier)
        
        return {
            "tier": tier.value,
            "limits": {
                "requests_per_minute": config.requests_per_minute,
                "chat_messages_per_minute": config.chat_messages_per_minute,
                "memory_operations_per_minute": config.memory_operations_per_minute,
                "agent_executions_per_hour": config.agent_executions_per_hour,
            },
            "usage": {
                "requests": await self._backend.get_usage(user_id, "request", 60),
                "chat": await self._backend.get_usage(user_id, "chat", 60),
                "memory": await self._backend.get_usage(user_id, "memory", 60),
                "agent": await self._backend.get_usage(user_id, "agent", 3600),
            },
            "backend": self._backend_type,
        }
    
    def get_status(self) -> Dict:
        """Get rate limiter status."""
        return {
            "backend": self._backend_type,
            "redis_available": REDIS_AVAILABLE,
            "tiers": {
                tier.value: {
                    "requests_per_minute": config.requests_per_minute,
                    "chat_messages_per_minute": config.chat_messages_per_minute,
                }
                for tier, config in TIER_LIMITS.items()
            }
        }


# Global instance
rate_limiter = RateLimiter()


async def check_rate_limit(
    user_id: str,
    tier: str = "free",
    action: str = "request",
) -> RateLimitResult:
    """Convenience function to check rate limit."""
    user_tier = UserTier(tier.lower()) if tier else UserTier.FREE
    return await rate_limiter.check_request(user_id, user_tier, action)
