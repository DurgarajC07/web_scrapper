"""
URL normalization and canonicalization.
Ensures consistent URL representation across the crawl.
"""

from __future__ import annotations

import re
from urllib.parse import (
    urlparse,
    urlunparse,
    urljoin,
    parse_qs,
    urlencode,
    unquote,
    quote,
)

from w3lib.url import canonicalize_url
import tldextract

from utils.logger import get_logger

logger = get_logger("url_normalizer")


class URLNormalizer:
    """Normalizes and validates URLs for consistent crawling."""

    # Parameters commonly used for tracking, not content
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "utm_id", "fbclid", "gclid", "gclsrc",
        "dclid", "msclkid", "twclid", "ref", "ref_src",
        "source", "mc_cid", "mc_eid", "si", "spm",
        "_ga", "_gl", "_hsenc", "_hsmi", "hsa_cam",
        "hsa_grp", "hsa_mt", "hsa_src", "hsa_ad", "hsa_acc",
        "hsa_net", "hsa_ver", "hsa_kw", "hsa_tgt", "hsa_la",
        "hsa_ol",
    }

    # Schemes we handle
    ALLOWED_SCHEMES = {"http", "https"}

    def __init__(
        self,
        remove_tracking_params: bool = True,
        remove_fragments: bool = True,
        sort_query_params: bool = True,
    ):
        self.remove_tracking = remove_tracking_params
        self.remove_fragments = remove_fragments
        self.sort_params = sort_query_params

    def normalize(self, url: str, base_url: str | None = None) -> str | None:
        """
        Fully normalize a URL.
        Returns None if URL is invalid or not crawlable.
        """
        try:
            # Resolve relative URLs
            if base_url and not url.startswith(("http://", "https://")):
                url = urljoin(base_url, url)

            # Decode and re-encode properly
            url = unquote(url)

            parsed = urlparse(url)

            # Validate scheme
            if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
                return None

            # Skip non-web resources in URL
            skip_patterns = [
                "javascript:", "mailto:", "tel:", "data:",
                "ftp:", "file:", "blob:",
            ]
            if any(url.lower().startswith(p) for p in skip_patterns):
                return None

            # Normalize scheme
            scheme = parsed.scheme.lower()

            # Normalize host
            hostname = parsed.hostname
            if not hostname:
                return None
            hostname = hostname.lower().strip(".")

            # Remove default ports
            port = parsed.port
            if (scheme == "http" and port == 80) or (
                scheme == "https" and port == 443
            ):
                port = None

            netloc = hostname
            if port:
                netloc = f"{hostname}:{port}"
            if parsed.username:
                user_info = parsed.username
                if parsed.password:
                    user_info += f":{parsed.password}"
                netloc = f"{user_info}@{netloc}"

            # Normalize path
            path = parsed.path or "/"
            path = self._normalize_path(path)

            # Handle query parameters
            query = self._normalize_query(parsed.query)

            # Handle fragment
            fragment = "" if self.remove_fragments else parsed.fragment

            # Reassemble
            normalized = urlunparse((
                scheme,
                netloc,
                path,
                parsed.params,
                query,
                fragment,
            ))

            return normalized

        except Exception as e:
            logger.debug("url_normalization_failed", url=url, error=str(e))
            return None

    def _normalize_path(self, path: str) -> str:
        """Normalize URL path component."""
        # Remove duplicate slashes
        path = re.sub(r"/+", "/", path)

        # Resolve . and ..
        segments = path.split("/")
        resolved = []
        for seg in segments:
            if seg == ".":
                continue
            elif seg == ".." and resolved and resolved[-1] != "":
                resolved.pop()
            else:
                resolved.append(seg)

        path = "/".join(resolved)
        if not path.startswith("/"):
            path = "/" + path

        # Remove trailing slash (except for root)
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Properly encode path
        path = quote(path, safe="/:@!$&'()*+,;=-._~")

        return path

    def _normalize_query(self, query: str) -> str:
        """Normalize query string."""
        if not query:
            return ""

        params = parse_qs(query, keep_blank_values=True)

        # Remove tracking parameters
        if self.remove_tracking:
            params = {
                k: v
                for k, v in params.items()
                if k.lower() not in self.TRACKING_PARAMS
            }

        if not params:
            return ""

        # Sort parameters
        if self.sort_params:
            sorted_params = sorted(params.items())
        else:
            sorted_params = list(params.items())

        # Reconstruct
        parts = []
        for key, values in sorted_params:
            for value in sorted(values):
                parts.append((key, value))

        return urlencode(parts)

    def get_domain(self, url: str) -> str:
        """Extract registered domain from URL."""
        extracted = tldextract.extract(url)
        return f"{extracted.domain}.{extracted.suffix}"

    def get_subdomain(self, url: str) -> str:
        """Extract full subdomain from URL."""
        extracted = tldextract.extract(url)
        if extracted.subdomain:
            return f"{extracted.subdomain}.{extracted.domain}.{extracted.suffix}"
        return f"{extracted.domain}.{extracted.suffix}"

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same registered domain."""
        return self.get_domain(url1) == self.get_domain(url2)

    def is_same_subdomain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same subdomain."""
        return self.get_subdomain(url1) == self.get_subdomain(url2)

    def is_internal_link(
        self,
        url: str,
        base_url: str,
        include_subdomains: bool = True,
    ) -> bool:
        """Determine if URL is internal relative to base."""
        if include_subdomains:
            return self.is_same_domain(url, base_url)
        return self.is_same_subdomain(url, base_url)

    def make_absolute(self, url: str, base_url: str) -> str:
        """Convert relative URL to absolute."""
        if url.startswith(("http://", "https://")):
            return url
        return urljoin(base_url, url)