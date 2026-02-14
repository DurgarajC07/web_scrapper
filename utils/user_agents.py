"""
User agent rotation with realistic browser fingerprints.
"""

import random
from dataclasses import dataclass


@dataclass
class BrowserProfile:
    user_agent: str
    accept_language: str
    accept_encoding: str
    accept: str
    platform: str


# Comprehensive, up-to-date user agent list
USER_AGENTS = [
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        accept_language="en-US,en;q=0.9",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        platform="Windows",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        accept_language="en-US,en;q=0.9",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        platform="macOS",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        accept_language="en-US,en;q=0.9",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        platform="Linux",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
            "Gecko/20100101 Firefox/122.0"
        ),
        accept_language="en-US,en;q=0.5",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        platform="Windows",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.2.1 Safari/605.1.15"
        ),
        accept_language="en-US,en;q=0.9",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        platform="macOS",
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
        ),
        accept_language="en-US,en;q=0.9",
        accept_encoding="gzip, deflate, br",
        accept=(
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,image/apng,*/*;q=0.8"
        ),
        platform="Windows",
    ),
]


class UserAgentRotator:
    """Rotates user agents to mimic real browser diversity."""

    def __init__(self, profiles: list[BrowserProfile] | None = None):
        self._profiles = profiles or USER_AGENTS
        self._index = 0

    def get_random(self) -> BrowserProfile:
        return random.choice(self._profiles)

    def get_next(self) -> BrowserProfile:
        profile = self._profiles[self._index % len(self._profiles)]
        self._index += 1
        return profile

    def get_headers(self, profile: BrowserProfile | None = None) -> dict[str, str]:
        p = profile or self.get_random()
        return {
            "User-Agent": p.user_agent,
            "Accept": p.accept,
            "Accept-Language": p.accept_language,
            "Accept-Encoding": p.accept_encoding,
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }