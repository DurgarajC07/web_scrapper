"""
Main crawler engine orchestrating all components.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from config import CrawlConfig, IAWICConfig
from core.rate_limiter import AdaptiveRateLimiter
from core.robots_parser import RobotsParser
from core.session_manager import SessionManager
from core.url_frontier import URLFrontier, URLPriority
from core.url_normalizer import URLNormalizer
from extraction.content_extractor import ContentClassifier
from extraction.entity_extractor import EntityExtractor
from extraction.link_extractor import LinkExtractor
from extraction.metadata_extractor import MetadataExtractor
from intelligence.content_cleaner import ContentCleaner
from intelligence.language_detector import LanguageDetector
from intelligence.similarity_detector import SimilarityDetector
from rendering.renderer import PlaywrightRenderer
from rendering.static_fetcher import StaticFetcher
from utils.logger import get_logger

logger = get_logger("crawler_engine")


class CrawlerEngine:
    """Main crawler orchestration engine."""

    def __init__(self, config: IAWICConfig):
        """
        Initialize crawler engine.
        
        Args:
            config: IAWIC configuration
        """
        self.config = config
        self.crawl_config = config.crawl

        # Core components
        self.frontier = URLFrontier(
            max_depth=self.crawl_config.crawl_depth,
            max_urls=self.crawl_config.max_pages,
        )
        self.rate_limiter = AdaptiveRateLimiter(
            requests_per_second=self.crawl_config.requests_per_second,
            min_delay=self.crawl_config.min_delay,
            max_delay=self.crawl_config.max_delay,
            adaptive=self.crawl_config.adaptive_delay,
        )
        self.robots_parser = RobotsParser()
        self.session_manager = SessionManager()
        self.url_normalizer = URLNormalizer()

        # Extractors
        self.link_extractor = LinkExtractor(
            normalizer=self.url_normalizer,
            include_subdomains=self.crawl_config.include_subdomains,
        )
        self.metadata_extractor = MetadataExtractor()
        self.entity_extractor = EntityExtractor()
        self.content_classifier = ContentClassifier()

        # Intelligence
        self.content_cleaner = ContentCleaner()
        self.language_detector = LanguageDetector()
        self.similarity_detector = SimilarityDetector(
            threshold=self.crawl_config.similarity_threshold
        )

        # Rendering
        self.static_fetcher = StaticFetcher(
            timeout=self.crawl_config.page_timeout,
        )
        self.playwright_renderer: PlaywrightRenderer | None = None
        if self.crawl_config.render_mode in ("javascript", "auto"):
            self.playwright_renderer = PlaywrightRenderer(
                timeout=self.crawl_config.render_timeout * 1000,  # Convert to ms
            )

        # HTTP client
        self.client: httpx.AsyncClient | None = None

        # Statistics
        self.stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "start_time": None,
            "end_time": None,
        }

        self._running = False
        self._workers: list[asyncio.Task] = []

    async def start(self, seed_url: str) -> None:
        """
        Start crawling from seed URL.
        
        Args:
            seed_url: Starting URL
        """
        logger.info("crawler_starting", seed_url=seed_url)
        self.stats["start_time"] = datetime.utcnow()
        self._running = True

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.crawl_config.page_timeout),
            follow_redirects=True,
        )
        self.session_manager.apply_to_client(self.client)

        # Add seed URL
        await self.frontier.add(
            seed_url,
            depth=0,
            priority=URLPriority.CRITICAL,
        )

        # Start worker tasks
        num_workers = self.config.workers
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]

        # Wait for completion
        await asyncio.gather(*self._workers, return_exceptions=True)

        # Cleanup
        await self.stop()

    async def stop(self) -> None:
        """Stop crawler and cleanup."""
        self._running = False
        self.stats["end_time"] = datetime.utcnow()

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        # Close HTTP client
        if self.client:
            await self.client.aclose()

        # Close Playwright renderer
        if self.playwright_renderer:
            await self.playwright_renderer.close()

        logger.info("crawler_stopped", stats=self.get_stats())

    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes URLs from frontier."""
        logger.debug("worker_started", worker_id=worker_id)

        while self._running:
            # Get next URL
            entry = await self.frontier.get(timeout=2.0)
            if not entry:
                # Check if we should stop
                if self.frontier.is_empty:
                    break
                continue

            url = entry.url
            depth = entry.depth

            try:
                # Crawl page
                result = await self._crawl_page(url, depth)

                if result:
                    await self.frontier.mark_crawled(url)
                    self.stats["pages_crawled"] += 1

                    # Extract and add links
                    if result.get("links"):
                        await self._process_links(
                            result["links"],
                            url,
                            depth + 1,
                        )
                else:
                    self.stats["pages_failed"] += 1

            except Exception as e:
                logger.error("crawl_error", url=url, error=str(e))
                self.stats["pages_failed"] += 1

                # Retry logic
                should_retry = await self.frontier.mark_failed(url)
                if should_retry:
                    await self.frontier.add(
                        url,
                        depth=depth,
                        priority=URLPriority.LOW,
                    )

        logger.debug("worker_stopped", worker_id=worker_id)

    async def _crawl_page(self, url: str, depth: int) -> dict | None:
        """
        Crawl single page.
        
        Returns:
            Page data dict or None if failed
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # Check robots.txt
        if self.crawl_config.respect_robots_txt:
            can_fetch = await self.robots_parser.can_fetch(url, "IAWIC")
            if not can_fetch:
                logger.debug("robots_blocked", url=url)
                return None

            # Apply crawl delay from robots.txt
            crawl_delay = await self.robots_parser.get_crawl_delay(url, "IAWIC")
            if crawl_delay:
                self.rate_limiter.set_crawl_delay(domain, crawl_delay)

        # Rate limiting
        await self.rate_limiter.acquire(domain)

        # Fetch page - try static first, then JavaScript if needed
        start_time = asyncio.get_event_loop().time()
        html = None
        status_code = 0
        
        try:
            # Try static fetch first
            fetch_result = await self.static_fetcher.fetch(url)
            response_time = fetch_result.response_time
            status_code = fetch_result.status_code
            html = fetch_result.html

            # Record for rate limiter
            self.rate_limiter.record(
                domain,
                response_time,
                success=fetch_result.success,
                status_code=status_code,
            )

            if not fetch_result.success:
                logger.warning("http_error", url=url, status=status_code)
                return None

            # Check if we need JavaScript rendering
            needs_js_render = False
            if self.crawl_config.render_mode == "javascript":
                needs_js_render = True
            elif self.crawl_config.render_mode == "auto":
                # Auto-detect if page needs JS rendering
                # Check if page has very little content or no links
                if len(html) < 1000 or '<a' not in html:
                    needs_js_render = True

            # Use Playwright if needed
            if needs_js_render and self.playwright_renderer:
                logger.info("using_js_rendering", url=url)
                render_result = await self.playwright_renderer.render(url)
                if render_result.success:
                    html = render_result.html
                    status_code = render_result.status_code
                else:
                    logger.warning("js_render_failed", url=url, error=render_result.error)
                    # Fall back to static HTML
                    
        except Exception as e:
            logger.error("fetch_failed", url=url, error=str(e))
            return None

        # Extract data
        page_data = await self._extract_page_data(url, html, depth)

        return page_data

    async def _extract_page_data(
        self, url: str, html: str, depth: int
    ) -> dict:
        """Extract all data from page."""
        # Metadata
        metadata = self.metadata_extractor.extract(html, url)

        # Clean content
        cleaned = self.content_cleaner.clean(
            html,
            extract_main=self.crawl_config.enable_content_cleaning,
        )

        # Links
        links = self.link_extractor.extract(html, url)

        # Entities
        entities = self.entity_extractor.extract(html, cleaned["text"])

        # Language
        language = None
        if self.crawl_config.enable_language_detection:
            language = self.language_detector.detect(html, cleaned["text"])

        # Classification
        classification = None
        if self.crawl_config.enable_classification:
            classification = self.content_classifier.classify(html, url)

        # Build page data
        page_data = {
            "url": url,
            "domain": urlparse(url).netloc,
            "depth": depth,
            "title": metadata.title,
            "description": metadata.description,
            "text_content": cleaned["text"] if self.crawl_config.extract_text_content else "",
            "html": html if self.crawl_config.store_html else "",
            "metadata": {
                "canonical_url": metadata.canonical_url,
                "language": metadata.language,
                "author": metadata.author,
                "keywords": metadata.keywords,
                "og": metadata.og,
                "twitter": metadata.twitter,
            },
            "links": {
                "internal": links.internal,
                "external": links.external,
            },
            "entities": {
                "emails": entities.emails,
                "phones": entities.phones,
                "social_links": entities.social_links,
            },
            "language_detected": language,
            "classification": classification,
        }

        return page_data

    async def _process_links(
        self, links: dict, parent_url: str, depth: int
    ) -> None:
        """Process extracted links and add to frontier."""
        internal_links = links.get("internal", [])

        # Add internal links to frontier
        for link in internal_links:
            await self.frontier.add(
                link,
                depth=depth,
                priority=URLPriority.NORMAL,
                parent_url=parent_url,
            )

        # Optionally add external links
        if self.crawl_config.follow_external_links:
            external_links = links.get("external", [])
            for link in external_links[:10]:  # Limit external links
                await self.frontier.add(
                    link,
                    depth=depth,
                    priority=URLPriority.DEFERRED,
                    parent_url=parent_url,
                )

    def get_stats(self) -> dict:
        """Get crawler statistics."""
        stats = self.stats.copy()
        stats["frontier"] = self.frontier.get_stats()
        
        if stats["start_time"] and stats["end_time"]:
            duration = (stats["end_time"] - stats["start_time"]).total_seconds()
            stats["duration_seconds"] = duration
            if duration > 0:
                stats["pages_per_second"] = stats["pages_crawled"] / duration

        return stats
