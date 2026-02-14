"""
Session and cookie management for authenticated crawling.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field

import httpx

from utils.logger import get_logger

logger = get_logger("session_manager")


@dataclass
class SessionConfig:
    """Session configuration for authenticated crawling."""
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    auth: tuple[str, str] | None = None
    bearer_token: str | None = None


class SessionManager:
    """Manages HTTP sessions with cookie and auth support."""

    def __init__(self):
        self._cookies: dict[str, str] = {}
        self._custom_headers: dict[str, str] = {}
        self._auth: tuple[str, str] | None = None
        self._bearer_token: str | None = None

    def load_cookies_from_file(self, path: str):
        """Load cookies from a JSON file."""
        try:
            with open(path) as f:
                cookies = json.load(f)
            self._cookies.update(cookies)
            logger.info(
                "cookies_loaded",
                source=path,
                count=len(cookies),
            )
        except Exception as e:
            logger.error("cookie_load_failed", path=path, error=str(e))

    def load_cookies_from_dict(self, cookies: dict[str, str]):
        """Load cookies from a dictionary."""
        self._cookies.update(cookies)

    def set_auth(self, username: str, password: str):
        """Set basic authentication credentials."""
        self._auth = (username, password)

    def set_bearer_token(self, token: str):
        """Set bearer token for API authentication."""
        self._bearer_token = token
        self._custom_headers["Authorization"] = f"Bearer {token}"

    def set_custom_headers(self, headers: dict[str, str]):
        """Set additional custom headers."""
        self._custom_headers.update(headers)

    def apply_to_client(self, client: httpx.AsyncClient) -> httpx.AsyncClient:
        """Apply session config to httpx client."""
        if self._cookies:
            for name, value in self._cookies.items():
                client.cookies.set(name, value)

        if self._custom_headers:
            client.headers.update(self._custom_headers)

        return client

    def get_cookies(self) -> dict[str, str]:
        return self._cookies.copy()

    def get_headers(self) -> dict[str, str]:
        return self._custom_headers.copy()

    def get_auth(self) -> tuple[str, str] | None:
        return self._auth

    def get_playwright_cookies(self, domain: str) -> list[dict]:
        """Convert cookies to Playwright format."""
        pw_cookies = []
        for name, value in self._cookies.items():
            pw_cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
            })
        return pw_cookies