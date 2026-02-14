"""
Redis-based URL queue for crawler frontier.
"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from utils.logger import get_logger

logger = get_logger("redis_queue")


class RedisQueue:
    """Async Redis-based priority queue for URLs."""

    def __init__(self, uri: str, queue_name: str = "crawl_queue"):
        """
        Initialize Redis queue.
        
        Args:
            uri: Redis connection URI
            queue_name: Name of the queue
        """
        self.uri = uri
        self.queue_name = queue_name
        self.seen_set = f"{queue_name}:seen"
        self.client: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.client = await redis.from_url(self.uri, decode_responses=True)
            await self.client.ping()
            logger.info("redis_connected")
        except RedisError as e:
            logger.error("redis_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("redis_disconnected")

    async def push(self, url: str, priority: float = 0.0) -> bool:
        """
        Add URL to queue with priority.
        
        Args:
            url: URL to add
            priority: Priority score (higher = more important)
            
        Returns:
            True if added, False if already seen
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        # Check if already seen
        if await self.is_seen(url):
            return False

        # Add to seen set
        await self.client.sadd(self.seen_set, url)

        # Add to priority queue (sorted set)
        await self.client.zadd(self.queue_name, {url: priority})
        
        logger.debug("url_queued", url=url, priority=priority)
        return True

    async def pop(self, count: int = 1) -> list[str]:
        """
        Pop highest priority URLs from queue.
        
        Args:
            count: Number of URLs to pop
            
        Returns:
            List of URLs (may be fewer than count if queue is small)
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        # Get highest priority items (ZREVRANGE returns highest scores first)
        urls = await self.client.zrevrange(self.queue_name, 0, count - 1)
        
        if urls:
            # Remove from queue
            await self.client.zrem(self.queue_name, *urls)
        
        return urls

    async def peek(self, count: int = 10) -> list[tuple[str, float]]:
        """
        Peek at top URLs without removing them.
        
        Args:
            count: Number of URLs to peek
            
        Returns:
            List of (url, priority) tuples
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        # Get with scores
        items = await self.client.zrevrange(
            self.queue_name, 0, count - 1, withscores=True
        )
        
        return [(url, score) for url, score in items]

    async def is_seen(self, url: str) -> bool:
        """Check if URL has been seen before."""
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        return await self.client.sismember(self.seen_set, url)

    async def mark_seen(self, url: str) -> None:
        """Mark URL as seen without adding to queue."""
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        await self.client.sadd(self.seen_set, url)

    async def size(self) -> int:
        """Get queue size."""
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        return await self.client.zcard(self.queue_name)

    async def seen_count(self) -> int:
        """Get count of seen URLs."""
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        return await self.client.scard(self.seen_set)

    async def clear(self) -> None:
        """Clear queue and seen set."""
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        await self.client.delete(self.queue_name, self.seen_set)
        logger.info("queue_cleared")

    async def stats(self) -> dict:
        """Get queue statistics."""
        return {
            "queue_size": await self.size(),
            "seen_count": await self.seen_count(),
        }

    async def bulk_push(self, urls: list[tuple[str, float]]) -> int:
        """
        Bulk add URLs with priorities.
        
        Args:
            urls: List of (url, priority) tuples
            
        Returns:
            Number of URLs added (excluding duplicates)
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")

        added = 0
        
        # Filter out already seen URLs
        new_urls = []
        for url, priority in urls:
            if not await self.is_seen(url):
                new_urls.append((url, priority))
                await self.client.sadd(self.seen_set, url)
                added += 1

        if new_urls:
            # Bulk add to sorted set
            mapping = {url: priority for url, priority in new_urls}
            await self.client.zadd(self.queue_name, mapping)

        return added
