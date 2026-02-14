"""
Metadata extraction: titles, descriptions, OpenGraph, Twitter Cards, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from utils.logger import get_logger

logger = get_logger("metadata_extractor")


@dataclass
class PageMetadata:
    """Extracted page metadata."""
    title: str = ""
    description: str = ""
    canonical_url: str = ""
    language: str = ""
    charset: str = ""
    author: str = ""
    keywords: list[str] = field(default_factory=list)
    robots: str = ""
    favicon: str = ""
    og: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)
    other_meta: dict[str, str] = field(default_factory=dict)


class MetadataExtractor:
    """Extracts all metadata from HTML pages."""

    def extract(self, html: str, url: str = "") -> PageMetadata:
        """Extract all metadata from HTML."""
        soup = BeautifulSoup(html, "lxml")
        meta = PageMetadata()

        # Title
        meta.title = self._extract_title(soup)

        # Meta tags
        meta.description = self._get_meta_content(soup, "description")
        meta.author = self._get_meta_content(soup, "author")
        meta.robots = self._get_meta_content(soup, "robots")
        meta.charset = self._extract_charset(soup)

        # Keywords
        keywords_str = self._get_meta_content(soup, "keywords")
        if keywords_str:
            meta.keywords = [
                k.strip() for k in keywords_str.split(",") if k.strip()
            ]

        # Canonical URL
        meta.canonical_url = self._extract_canonical(soup)

        # Language
        meta.language = self._extract_language(soup)

        # Favicon
        meta.favicon = self._extract_favicon(soup, url)

        # OpenGraph
        meta.og = self._extract_og_tags(soup)

        # Twitter Cards
        meta.twitter = self._extract_twitter_tags(soup)

        # Other meta tags
        meta.other_meta = self._extract_other_meta(soup)

        return meta

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Fallback to og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Fallback to first H1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _get_meta_content(
        self, soup: BeautifulSoup, name: str
    ) -> str:
        """Get content attribute from meta tag by name."""
        # Try name attribute
        tag = soup.find("meta", attrs={"name": name})
        if not tag:
            tag = soup.find(
                "meta", attrs={"name": name.capitalize()}
            )
        if not tag:
            # Try property attribute
            tag = soup.find("meta", attrs={"property": name})

        if tag and isinstance(tag, Tag):
            return tag.get("content", "").strip()
        return ""

    def _extract_charset(self, soup: BeautifulSoup) -> str:
        """Extract character set."""
        # <meta charset="...">
        meta = soup.find("meta", attrs={"charset": True})
        if meta and isinstance(meta, Tag):
            return meta["charset"]

        # <meta http-equiv="Content-Type" content="text/html; charset=...">
        meta = soup.find(
            "meta", attrs={"http-equiv": "Content-Type"}
        )
        if meta and isinstance(meta, Tag):
            content = meta.get("content", "")
            if "charset=" in content:
                return content.split("charset=")[-1].strip()

        return "utf-8"

    def _extract_canonical(self, soup: BeautifulSoup) -> str:
        """Extract canonical URL."""
        link = soup.find("link", attrs={"rel": "canonical"})
        if link and isinstance(link, Tag):
            return link.get("href", "").strip()
        return ""

    def _extract_language(self, soup: BeautifulSoup) -> str:
        """Extract page language."""
        # <html lang="...">
        html_tag = soup.find("html")
        if html_tag and isinstance(html_tag, Tag):
            lang = html_tag.get("lang", "")
            if lang:
                return lang.strip()

        # <meta http-equiv="content-language">
        meta = soup.find(
            "meta", attrs={"http-equiv": "content-language"}
        )
        if meta and isinstance(meta, Tag):
            return meta.get("content", "").strip()

        return ""

    def _extract_favicon(
        self, soup: BeautifulSoup, base_url: str
    ) -> str:
        """Extract favicon URL."""
        icon_rels = [
            "icon",
            "shortcut icon",
            "apple-touch-icon",
            "apple-touch-icon-precomposed",
        ]

        for rel in icon_rels:
            link = soup.find("link", attrs={"rel": rel})
            if not link:
                link = soup.find(
                    "link", attrs={"rel": lambda x: x and rel in str(x).lower()}
                )
            if link and isinstance(link, Tag):
                href = link.get("href", "")
                if href:
                    return href.strip()

        return ""

    def _extract_og_tags(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract OpenGraph meta tags."""
        og = {}
        for tag in soup.find_all("meta", attrs={"property": True}):
            prop = tag.get("property", "")
            if prop.startswith("og:"):
                key = prop[3:]  # Remove 'og:' prefix
                og[key] = tag.get("content", "").strip()
        return og

    def _extract_twitter_tags(
        self, soup: BeautifulSoup
    ) -> dict[str, str]:
        """Extract Twitter Card meta tags."""
        twitter = {}
        for tag in soup.find_all("meta", attrs={"name": True}):
            name = tag.get("name", "")
            if name.startswith("twitter:"):
                key = name[8:]  # Remove 'twitter:' prefix
                twitter[key] = tag.get("content", "").strip()
        return twitter

    def _extract_other_meta(
        self, soup: BeautifulSoup
    ) -> dict[str, str]:
        """Extract other meta tags not covered above."""
        other = {}
        skip_names = {
            "description", "author", "keywords", "robots",
            "viewport", "charset",
        }
        skip_prefixes = ("og:", "twitter:", "fb:", "article:")

        for tag in soup.find_all("meta", attrs={"name": True}):
            name = tag.get("name", "").lower()
            if name in skip_names:
                continue
            if any(name.startswith(p) for p in skip_prefixes):
                continue
            content = tag.get("content", "").strip()
            if content:
                other[name] = content

        return other