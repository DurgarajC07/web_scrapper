"""
Robots.txt parser with caching and crawl-delay support.
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from dataclasses import dataclass, field

import httpx

from utils.logger import get_logger
from utils.user_agents import UserAgentRotator

logger = get_logger("robots_parser")


@dataclass
class RobotsData:
    """Parsed robots.txt information."""

    raw_content: str = ""
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    disallowed_paths: list[str] = field(default_factory=list)
    fetch_time: float = 0.0
    is_loaded: bool = False


class RobotsParser:
    """
    Async robots.txt parser that respects crawling rules.
    Caches parsed data per domain.
    """

    def __init__(
        self,
        user_agent: str = "*",
        cache_ttl: int = 3600,
    ):
        self._user_agent = user_agent
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[RobotsData, RobotFileParser]] = {}
        self._ua_rotator = UserAgentRotator()

    async def fetch_and_parse(
        self,
        base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> RobotsData:
        """Fetch and parse robots.txt for a given base URL."""
        parsed_url = urlparse(base_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        domain = parsed_url.netloc

        # Check cache
        if domain in self._cache:
            data, _ = self._cache[domain]
            if time.time() - data.fetch_time < self._cache_ttl:
                return data

        data = RobotsData()
        parser = RobotFileParser()

        try:
            should_close = False
            if client is None:
                client = httpx.AsyncClient(
                    timeout=15,
                    follow_redirects=True,
                    headers=self._ua_rotator.get_headers(),
                )
                should_close = True

            try:
                response = await client.get(robots_url)

                if response.status_code == 200:
                    data.raw_content = response.text
                    data.is_loaded = True

                    # Parse with stdlib parser
                    parser.parse(data.raw_content.splitlines())

                    # Extract sitemaps
                    data.sitemaps = self._extract_sitemaps(data.raw_content)

                    # Extract crawl delay
                    data.crawl_delay = self._extract_crawl_delay(
                        data.raw_content
                    )

                    # Extract paths
                    data.allowed_paths = self._extract_paths(
                        data.raw_content, "allow"
                    )
                    data.disallowed_paths = self._extract_paths(
                        data.raw_content, "disallow"
                    )

                    logger.info(
                        "robots_txt_loaded",
                        domain=domain,
                        sitemaps=len(data.sitemaps),
                        crawl_delay=data.crawl_delay,
                    )

                elif response.status_code in (404, 410):
                    # No robots.txt — everything is allowed
                    data.is_loaded = True
                    logger.info("robots_txt_not_found", domain=domain)

                else:
                    logger.warning(
                        "robots_txt_fetch_error",
                        domain=domain,
                        status=response.status_code,
                    )
            finally:
                if should_close:
                    await client.aclose()

        except Exception as e:
            logger.warning(
                "robots_txt_fetch_exception",
                domain=domain,
                error=str(e),
            )

        data.fetch_time = time.time()
        self._cache[domain] = (data, parser)
        return data

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc

        if domain not in self._cache:
            # Not yet loaded — allow by default
            return True

        data, parser = self._cache[domain]

        # If robots.txt was not found (404/410), allow everything
        if not data.raw_content:
            return True

        try:
            return parser.can_fetch(self._user_agent, url)
        except Exception:
            return True

    def get_crawl_delay(self, url: str) -> float | None:
        """Get crawl delay for domain."""
        parsed = urlparse(url)
        domain = parsed.netloc

        if domain in self._cache:
            data, _ = self._cache[domain]
            return data.crawl_delay
        return None

    def get_sitemaps(self, url: str) -> list[str]:
        """Get sitemap URLs from robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc

        if domain in self._cache:
            data, _ = self._cache[domain]
            return data.sitemaps
        return []

    def _extract_sitemaps(self, content: str) -> list[str]:
        sitemaps = []
        for line in content.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    sitemaps.append(url)
        return sitemaps

    def _extract_crawl_delay(self, content: str) -> float | None:
        for line in content.splitlines():
            line = line.strip().lower()
            if line.startswith("crawl-delay:"):
                try:
                    return float(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
        return None

    def _extract_paths(self, content: str, directive: str) -> list[str]:
        paths = []
        directive_lower = directive.lower()
        for line in content.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith(f"{directive_lower}:"):
                path = line.strip().split(":", 1)[1].strip()
                if path:
                    paths.append(path)
        return paths

    # Async wrapper methods for crawler engine compatibility
    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Async wrapper to check if URL can be fetched.
        Fetches robots.txt if not already cached.
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        # Fetch robots.txt if not in cache
        if domain not in self._cache:
            await self.fetch_and_parse(url)

        return self.is_allowed(url)

    async def get_crawl_delay(self, url: str, user_agent: str = "*") -> float | None:
        """
        Async wrapper to get crawl delay.
        Fetches robots.txt if not already cached.
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        # Fetch robots.txt if not in cache
        if domain not in self._cache:
            await self.fetch_and_parse(url)

        if domain in self._cache:
            data, _ = self._cache[domain]
            return data.crawl_delay
        return None