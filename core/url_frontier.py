"""
URL Frontier: Priority queue for managing URLs to crawl.
Implements BFS/DFS hybrid with intelligent prioritization.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from utils.hash_utils import url_hash
from utils.logger import get_logger

logger = get_logger("url_frontier")


class URLPriority(int, Enum):
    """URL crawl priority levels."""
    CRITICAL = 0   # Sitemaps, important pages
    HIGH = 1       # Main navigation pages
    NORMAL = 2     # Standard discovered links
    LOW = 3        # Deep pages, pagination
    DEFERRED = 4   # External links, low-value pages


@dataclass(order=True)
class URLEntry:
    """Single URL entry in the frontier."""
    priority: int
    depth: int = field(compare=False)
    url: str = field(compare=False)
    parent_url: str = field(compare=False, default="")
    discovered_at: float = field(compare=False, default_factory=time.time)
    retry_count: int = field(compare=False, default=0)
    metadata: dict = field(compare=False, default_factory=dict)


class URLFrontier:
    """
    Priority-based URL frontier with deduplication.
    Manages the queue of URLs to be crawled.
    """

    def __init__(
        self,
        max_depth: int = 3,
        max_urls: int = 10000,
    ):
        self._max_depth = max_depth
        self._max_urls = max_urls
        self._queue: list[URLEntry] = []
        self._seen_urls: set[str] = set()
        self._crawled_urls: set[str] = set()
        self._failed_urls: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

        # Statistics
        self._total_added = 0
        self._total_duplicates_skipped = 0

    async def add(
        self,
        url: str,
        depth: int = 0,
        priority: URLPriority = URLPriority.NORMAL,
        parent_url: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Add URL to frontier if not already seen."""
        async with self._lock:
            # Generate hash for dedup
            uhash = url_hash(url)

            # Skip if already seen
            if uhash in self._seen_urls:
                self._total_duplicates_skipped += 1
                return False

            # Skip if over depth limit
            if depth > self._max_depth:
                return False

            # Skip if queue is full
            if len(self._queue) >= self._max_urls:
                return False

            # Add to seen set
            self._seen_urls.add(uhash)

            # Create entry
            entry = URLEntry(
                priority=priority.value,
                depth=depth,
                url=url,
                parent_url=parent_url,
                metadata=metadata or {},
            )

            heapq.heappush(self._queue, entry)
            self._total_added += 1
            self._not_empty.set()

            return True

    async def add_many(
        self,
        urls: list[str],
        depth: int = 0,
        priority: URLPriority = URLPriority.NORMAL,
        parent_url: str = "",
    ) -> int:
        """Add multiple URLs. Returns count of actually added."""
        added = 0
        for url in urls:
            if await self.add(url, depth, priority, parent_url):
                added += 1
        return added

    async def get(self, timeout: float = 5.0) -> URLEntry | None:
        """Get next URL to crawl."""
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            if not self._queue:
                self._not_empty.clear()
                return None

            entry = heapq.heappop(self._queue)

            if not self._queue:
                self._not_empty.clear()

            return entry

    async def mark_crawled(self, url: str):
        """Mark URL as successfully crawled."""
        async with self._lock:
            self._crawled_urls.add(url_hash(url))

    async def mark_failed(self, url: str, max_retries: int = 3) -> bool:
        """Mark URL as failed. Returns True if should retry."""
        async with self._lock:
            uhash = url_hash(url)
            self._failed_urls[uhash] = self._failed_urls.get(uhash, 0) + 1
            return self._failed_urls[uhash] < max_retries

    def is_crawled(self, url: str) -> bool:
        return url_hash(url) in self._crawled_urls

    def is_seen(self, url: str) -> bool:
        return url_hash(url) in self._seen_urls

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def crawled_count(self) -> int:
        return len(self._crawled_urls)

    def get_stats(self) -> dict:
        return {
            "queue_size": self.size,
            "total_added": self._total_added,
            "total_crawled": self.crawled_count,
            "total_seen": len(self._seen_urls),
            "total_failed": len(self._failed_urls),
            "duplicates_skipped": self._total_duplicates_skipped,
        }