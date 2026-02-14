"""
JavaScript rendering engine using Playwright.
Handles dynamic content, SPAs, and lazy-loaded resources.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger
from utils.user_agents import UserAgentRotator

logger = get_logger("renderer")


@dataclass
class RenderResult:
    """Result of rendering a page with JS execution."""
    url: str
    final_url: str
    status_code: int
    html: str
    title: str
    response_time: float
    success: bool
    error: str | None = None
    is_blocked: bool = False
    blocked_reason: str | None = None
    screenshot: bytes | None = None
    console_logs: list[str] | None = None
    network_requests: list[dict] | None = None


class PlaywrightRenderer:
    """
    Renders pages using Playwright for full JavaScript execution.
    Handles infinite scroll, lazy loading, and click-to-load.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        take_screenshots: bool = False,
        capture_network: bool = False,
    ):
        self._headless = headless
        self._timeout = timeout
        self._viewport = {"width": viewport_width, "height": viewport_height}
        self._take_screenshots = take_screenshots
        self._capture_network = capture_network
        self._ua_rotator = UserAgentRotator()
        self._browser = None
        self._playwright = None

    async def initialize(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            logger.info("playwright_browser_initialized")

        except ImportError:
            logger.error(
                "playwright_not_installed",
                hint="Run: pip install playwright && playwright install chromium",
            )
            raise
        except Exception as e:
            logger.error("playwright_init_failed", error=str(e))
            raise

    async def close(self):
        """Close browser and Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("playwright_browser_closed")

    async def render(
        self,
        url: str,
        wait_for: str | None = None,
        scroll_to_bottom: bool = True,
        click_load_more: bool = True,
        cookies: list[dict] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> RenderResult:
        """Render a page with full JS execution."""
        if not self._browser:
            await self.initialize()

        start_time = time.time()
        console_logs: list[str] = []
        network_requests: list[dict] = []

        try:
            profile = self._ua_rotator.get_random()

            context = await self._browser.new_context(
                viewport=self._viewport,
                user_agent=profile.user_agent,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers=extra_headers or {},
            )

            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()

            # Capture console logs
            page.on("console", lambda msg: console_logs.append(
                f"[{msg.type}] {msg.text}"
            ))

            # Capture network requests
            if self._capture_network:
                page.on("request", lambda req: network_requests.append({
                    "url": req.url,
                    "method": req.method,
                    "resource_type": req.resource_type,
                }))

            # Block unnecessary resources for speed
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}",
                lambda route: route.abort()
                if not self._take_screenshots
                else route.continue_(),
            )

            # Navigate
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self._timeout,
            )

            status_code = response.status if response else 0

            # Wait for additional content
            if wait_for:
                try:
                    await page.wait_for_selector(
                        wait_for, timeout=5000
                    )
                except Exception:
                    pass

            # Handle infinite scroll and lazy loading
            if scroll_to_bottom:
                await self._scroll_to_bottom(page)

            # Handle "Load More" buttons
            if click_load_more:
                await self._click_load_more(page)

            # Wait for any remaining network activity
            try:
                await page.wait_for_load_state(
                    "networkidle", timeout=5000
                )
            except Exception:
                pass

            # Get final HTML
            html = await page.content()
            title = await page.title()
            final_url = page.url

            # Screenshot
            screenshot = None
            if self._take_screenshots:
                screenshot = await page.screenshot(full_page=True)

            # Check for blocking
            is_blocked, reason = self._detect_blocking(html, status_code)

            elapsed = time.time() - start_time

            await context.close()

            result = RenderResult(
                url=url,
                final_url=final_url,
                status_code=status_code,
                html=html,
                title=title,
                response_time=elapsed,
                success=200 <= status_code < 400,
                is_blocked=is_blocked,
                blocked_reason=reason,
                screenshot=screenshot,
                console_logs=console_logs if console_logs else None,
                network_requests=(
                    network_requests if network_requests else None
                ),
            )

            logger.info(
                "page_rendered",
                url=url,
                status=status_code,
                time=f"{elapsed:.2f}s",
                html_size=len(html),
                blocked=is_blocked,
            )

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("render_failed", url=url, error=str(e))
            return RenderResult(
                url=url,
                final_url=url,
                status_code=0,
                html="",
                title="",
                response_time=elapsed,
                success=False,
                error=str(e),
            )

    async def _scroll_to_bottom(
        self,
        page: Any,
        max_scrolls: int = 10,
        scroll_delay: float = 1.0,
    ):
        """Progressively scroll to bottom to trigger lazy loading."""
        try:
            previous_height = 0
            for i in range(max_scrolls):
                current_height = await page.evaluate(
                    "document.body.scrollHeight"
                )

                if current_height == previous_height:
                    break

                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                await asyncio.sleep(scroll_delay)

                previous_height = current_height

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")

        except Exception as e:
            logger.debug("scroll_failed", error=str(e))

    async def _click_load_more(
        self,
        page: Any,
        max_clicks: int = 5,
    ):
        """Find and click 'Load More' style buttons."""
        load_more_selectors = [
            "button:has-text('Load More')",
            "button:has-text('Show More')",
            "button:has-text('View More')",
            "a:has-text('Load More')",
            "a:has-text('Show More')",
            "[class*='load-more']",
            "[class*='loadmore']",
            "[class*='show-more']",
            "[data-action='load-more']",
        ]

        for _ in range(max_clicks):
            clicked = False
            for selector in load_more_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await asyncio.sleep(2)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                break

    def _detect_blocking(
        self, html: str, status_code: int
    ) -> tuple[bool, str | None]:
        """Detect bot blocking in rendered page."""
        if status_code == 403:
            return True, "403_forbidden"
        if status_code == 429:
            return True, "429_rate_limited"

        html_lower = html[:10000].lower()
        blocking_patterns = [
            ("recaptcha", "recaptcha_detected"),
            ("g-recaptcha", "recaptcha_detected"),
            ("captcha-container", "captcha_detected"),
            ("cf-challenge", "cloudflare_challenge"),
            ("challenge-platform", "challenge_detected"),
            ("access denied", "access_denied"),
            ("bot detected", "bot_detected"),
        ]

        for pattern, reason in blocking_patterns:
            if pattern in html_lower:
                return True, reason

        return False, None