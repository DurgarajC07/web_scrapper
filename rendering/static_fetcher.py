"""
Static HTTP content fetcher with retry logic and error handling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from utils.user_agents import UserAgentRotator
from utils.logger import get_logger

logger = get_logger("static_fetcher")


@dataclass
class FetchResult:
    """Result of fetching a URL."""
    url: str
    status_code: int
    content_type: str
    html: str
    headers: dict[str, str]
    response_time: float
    final_url: str
    encoding: str
    content_length: int
    success: bool
    error: str | None = None
    is_blocked: bool = False
    blocked_reason: str | None = None


class StaticFetcher:
    """Fetches static web pages with robust error handling."""

    BLOCKED_INDICATORS = [
        "captcha",
        "recaptcha",
        "challenge",
        "access denied",
        "blocked",
        "bot detected",
        "please verify",
        "security check",
    ]

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        follow_redirects: bool = True,
        proxy_url: str | None = None,
    ):
        self._timeout = timeout
        self._max_retries = max_retries
        self._follow_redirects = follow_redirects
        self._proxy_url = proxy_url
        self._ua_rotator = UserAgentRotator()

    async def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> FetchResult:
        """Fetch a URL and return the result."""
        start_time = time.time()
        request_headers = self._ua_rotator.get_headers()
        if headers:
            request_headers.update(headers)

        transport_kwargs = {}
        if self._proxy_url:
            transport_kwargs["proxy"] = self._proxy_url

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=self._follow_redirects,
                http2=True,
                **transport_kwargs,
            ) as client:
                if cookies:
                    for name, value in cookies.items():
                        client.cookies.set(name, value)

                response = await client.get(url, headers=request_headers)
                elapsed = time.time() - start_time

                # Check for blocking
                is_blocked, reason = self._detect_blocking(response)

                html = response.text
                result = FetchResult(
                    url=url,
                    status_code=response.status_code,
                    content_type=response.headers.get(
                        "content-type", ""
                    ),
                    html=html,
                    headers=dict(response.headers),
                    response_time=elapsed,
                    final_url=str(response.url),
                    encoding=response.encoding or "utf-8",
                    content_length=len(html),
                    success=200 <= response.status_code < 400,
                    is_blocked=is_blocked,
                    blocked_reason=reason,
                )

                logger.info(
                    "page_fetched",
                    url=url,
                    status=response.status_code,
                    time=f"{elapsed:.2f}s",
                    size=len(html),
                    blocked=is_blocked,
                )

                return result

        except httpx.TimeoutException as e:
            elapsed = time.time() - start_time
            logger.warning("fetch_timeout", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                content_type="",
                html="",
                headers={},
                response_time=elapsed,
                final_url=url,
                encoding="utf-8",
                content_length=0,
                success=False,
                error=f"Timeout: {str(e)}",
            )

        except httpx.ConnectError as e:
            elapsed = time.time() - start_time
            logger.warning("fetch_connection_error", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                content_type="",
                html="",
                headers={},
                response_time=elapsed,
                final_url=url,
                encoding="utf-8",
                content_length=0,
                success=False,
                error=f"Connection error: {str(e)}",
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("fetch_error", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                content_type="",
                html="",
                headers={},
                response_time=elapsed,
                final_url=url,
                encoding="utf-8",
                content_length=0,
                success=False,
                error=str(e),
            )

    def _detect_blocking(
        self, response: httpx.Response
    ) -> tuple[bool, str | None]:
        """Detect if request was blocked by anti-bot measures."""
        # Check status code
        if response.status_code == 403:
            return True, "403_forbidden"
        if response.status_code == 429:
            return True, "429_rate_limited"
        if response.status_code == 503:
            # Could be Cloudflare challenge
            if "cloudflare" in response.headers.get("server", "").lower():
                return True, "cloudflare_challenge"

        # Check response body for captcha indicators
        body_lower = response.text[:5000].lower()
        for indicator in self.BLOCKED_INDICATORS:
            if indicator in body_lower:
                return True, f"blocked_indicator: {indicator}"

        return False, None