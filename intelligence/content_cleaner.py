"""
Content cleaning and main content extraction.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment
from readability import Document

from utils.logger import get_logger

logger = get_logger("content_cleaner")


class ContentCleaner:
    """Cleans HTML and extracts main content."""

    # Tags to remove completely
    REMOVE_TAGS = {
        "script", "style", "noscript", "iframe", "embed",
        "object", "applet", "canvas", "svg",
    }

    # Boilerplate selectors (navigation, ads, footers, etc.)
    BOILERPLATE_SELECTORS = [
        "nav", "header", "footer", "aside",
        "[role='navigation']", "[role='banner']", "[role='contentinfo']",
        ".nav", ".navigation", ".menu", ".sidebar",
        ".header", ".footer", ".advertisement", ".ad",
        ".social", ".share", ".related", ".comments",
        "#nav", "#navigation", "#menu", "#sidebar",
        "#header", "#footer", "#comments",
    ]

    def clean(self, html: str, extract_main: bool = True) -> dict:
        """
        Clean HTML and optionally extract main content.
        
        Returns:
            dict with 'cleaned_html', 'main_content', 'text'
        """
        if not html:
            return {
                "cleaned_html": "",
                "main_content": "",
                "text": "",
            }

        # Sanitize HTML to remove NULL bytes and control characters
        # that cause XML compatibility errors
        html = self._sanitize_html(html)

        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted tags
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove boilerplate
        for selector in self.BOILERPLATE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Extract main content using readability
        main_html = ""
        if extract_main:
            try:
                from readability import Document
                doc = Document(str(soup))
                main_html = doc.summary()
            except Exception as e:
                logger.warning("readability_failed", error=str(e))
                main_html = str(soup)

        # Clean attributes
        for tag in soup.find_all(True):
            # Keep only these attributes
            keep_attrs = {"href", "src", "alt", "title"}
            tag.attrs = {
                k: v for k, v in tag.attrs.items() if k in keep_attrs
            }

        cleaned_html = str(soup)
        text = self._extract_text(soup)

        return {
            "cleaned_html": cleaned_html,
            "main_content": main_html if extract_main else cleaned_html,
            "text": text,
        }

    def _sanitize_html(self, html: str) -> str:
        """
        Remove NULL bytes and control characters that cause XML errors.
        """
        # Remove NULL bytes
        html = html.replace('\x00', '')
        
        # Remove other control characters except newlines, tabs, carriage returns
        # Keep: \n (0x0A), \r (0x0D), \t (0x09)
        sanitized = []
        for char in html:
            code = ord(char)
            # Allow printable characters and safe whitespace
            if code >= 32 or code in (9, 10, 13):
                sanitized.append(char)
        
        return ''.join(sanitized)

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from soup."""
        # Get text
        text = soup.get_text(separator=" ", strip=True)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)

        return text.strip()

    def extract_paragraphs(self, html: str) -> list[str]:
        """Extract all paragraph text."""
        soup = BeautifulSoup(html, "lxml")
        paragraphs = []

        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 20:  # Filter out very short paragraphs
                paragraphs.append(text)

        return paragraphs

    def remove_boilerplate(self, html: str) -> str:
        """Remove boilerplate content only."""
        soup = BeautifulSoup(html, "lxml")

        for selector in self.BOILERPLATE_SELECTORS:
            for elem in soup.select(selector):
                elem.decompose()

        return str(soup)
