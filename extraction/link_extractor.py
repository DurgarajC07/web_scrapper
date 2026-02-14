"""
Link extraction and classification (internal vs external).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.url_normalizer import URLNormalizer
from utils.file_utils import is_webpage_url
from utils.logger import get_logger

logger = get_logger("link_extractor")


@dataclass
class LinkData:
    internal: list[str] = field(default_factory=list)
    external: list[str] = field(default_factory=list)
    all_links: list[dict] = field(default_factory=list)


class LinkExtractor:
    """Extracts and classifies links from HTML pages."""

    SKIP_SCHEMES = {
        "javascript", "mailto", "tel", "data",
        "ftp", "file", "blob", "sms",
    }

    def __init__(
        self,
        normalizer: URLNormalizer | None = None,
        include_subdomains: bool = True,
    ):
        self._normalizer = normalizer or URLNormalizer()
        self._include_subdomains = include_subdomains

    def extract(self, html: str, base_url: str) -> LinkData:
        """Extract all links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        link_data = LinkData()

        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            # Skip empty and fragment-only links
            if not href or href == "#" or href.startswith("#"):
                continue

            # Skip non-http schemes
            parsed_href = urlparse(href)
            if parsed_href.scheme and parsed_href.scheme.lower() in self.SKIP_SCHEMES:
                continue

            # Normalize
            normalized = self._normalizer.normalize(href, base_url)
            if not normalized:
                continue

            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # Classify
            is_internal = self._normalizer.is_internal_link(
                normalized, base_url, self._include_subdomains
            )

            # Get link text and attributes
            link_info = {
                "url": normalized,
                "text": a.get_text(strip=True)[:200],
                "title": a.get("title", ""),
                "rel": a.get("rel", []),
                "is_nofollow": "nofollow" in (a.get("rel") or []),
                "is_internal": is_internal,
            }

            link_data.all_links.append(link_info)

            if is_internal:
                link_data.internal.append(normalized)
            else:
                link_data.external.append(normalized)

        logger.debug(
            "links_extracted",
            url=base_url,
            internal=len(link_data.internal),
            external=len(link_data.external),
        )

        return link_data