"""
FastAPI dependencies for authentication, rate limiting, and database connections.
"""

from __future__ import annotations

import os
from typing import Optional

import redis.asyncio as redis
import structlog
from fastapi import Depends, Header, HTTPException, Request, status

from app.config import settings

logger = structlog.get_logger()

# Redis connection pool
_redis_pool: Optional[redis.ConnectionPool] = None


async def get_redis() -> redis.Redis:
    """
    Get Redis client with connection pooling.

    Returns:
        Async Redis client

    Raises:
        HTTPException: If Redis connection fails
    """
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )

    try:
        client = redis.Redis(connection_pool=_redis_pool)
        # Test connection
        await client.ping()
        return client
    except redis.ConnectionError as e:
        logger.error("Redis connection failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service unavailable",
        )


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Verify API key from request headers.

    Accepts API key from either X-API-Key header or Authorization Bearer token.

    Args:
        x_api_key: API key from X-API-Key header
        authorization: Authorization header (Bearer token)

    Returns:
        Valid API key

    Raises:
        HTTPException: If authentication fails
    """
    # Get configured API key
    valid_api_key = settings.API_KEY

    # If no API key is configured, allow all requests (development mode)
    if not valid_api_key:
        logger.warning("No API_KEY configured - authentication disabled")
        return "development"

    # Check X-API-Key header
    if x_api_key:
        if x_api_key == valid_api_key:
            return x_api_key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check Authorization header
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            if token == valid_api_key:
                return token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_api_key_optional(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Optionally verify API key (for public endpoints with rate limits).

    Returns:
        API key if provided and valid, None otherwise
    """
    valid_api_key = settings.API_KEY

    if not valid_api_key:
        return None

    if x_api_key and x_api_key == valid_api_key:
        return x_api_key

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token == valid_api_key:
            return token

    return None


def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.

    Handles proxied requests (X-Forwarded-For header).

    Args:
        request: FastAPI request object

    Returns:
        Client IP address
    """
    # Check for proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"


class RateLimitChecker:
    """
    Rate limit checker using Redis.
    """

    def __init__(
        self,
        requests_per_minute: int = 30,
        key_prefix: str = "ratelimit",
    ):
        """
        Initialize rate limit checker.

        Args:
            requests_per_minute: Maximum requests per minute
            key_prefix: Redis key prefix
        """
        self.requests_per_minute = requests_per_minute
        self.key_prefix = key_prefix
        self.window_seconds = 60

    async def check_rate_limit(
        self,
        identifier: str,
        redis_client: redis.Redis,
    ) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded.

        Args:
            identifier: Client identifier (IP or API key)
            redis_client: Redis client

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        key = f"{self.key_prefix}:{identifier}"

        # Get current count
        current = await redis_client.get(key)
        if current is None:
            # First request in window
            await redis_client.setex(key, self.window_seconds, 1)
            return True, self.requests_per_minute - 1

        current_count = int(current)
        if current_count >= self.requests_per_minute:
            return False, 0

        # Increment counter
        await redis_client.incr(key)
        return True, self.requests_per_minute - current_count - 1


# Global rate limiter instance
rate_limiter = RateLimitChecker(requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


async def check_rate_limit(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    """
    Dependency to check rate limit.

    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = get_client_ip(request)
    allowed, remaining = await rate_limiter.check_rate_limit(client_ip, redis_client)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

