"""
Entity extraction: emails, phone numbers, addresses, social links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger("entity_extractor")


@dataclass
class EntityData:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    social_links: list[dict[str, str]] = field(default_factory=list)


class EntityExtractor:
    """Extracts entities (emails, phones, social links) from pages."""

    # Regex patterns
    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    )

    PHONE_PATTERNS = [
        # International format
        re.compile(
            r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        ),
        # UK format
        re.compile(r"\+44\s?\d{4}\s?\d{6}"),
        # General international
        re.compile(r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"),
    ]

    SOCIAL_PLATFORMS = {
        "twitter": [r"twitter\.com/", r"x\.com/"],
        "facebook": [r"facebook\.com/", r"fb\.com/"],
        "instagram": [r"instagram\.com/"],
        "linkedin": [r"linkedin\.com/"],
        "youtube": [r"youtube\.com/", r"youtu\.be/"],
        "github": [r"github\.com/"],
        "tiktok": [r"tiktok\.com/"],
        "pinterest": [r"pinterest\.com/"],
        "reddit": [r"reddit\.com/"],
        "mastodon": [r"mastodon\.\w+/"],
    }

    # Common obfuscation patterns for emails
    EMAIL_OBFUSCATION = [
        (r"\[at\]", "@"),
        (r"\(at\)", "@"),
        (r" at ", "@"),
        (r"\[dot\]", "."),
        (r"\(dot\)", "."),
        (r" dot ", "."),
    ]

    def extract(self, html: str, text: str = "") -> EntityData:
        """Extract all entities from HTML and text content."""
        soup = BeautifulSoup(html, "lxml")
        entities = EntityData()

        # Combine sources
        full_text = text if text else soup.get_text()

        entities.emails = self._extract_emails(html, full_text, soup)
        entities.phones = self._extract_phones(full_text)
        entities.social_links = self._extract_social_links(soup)
        entities.addresses = self._extract_addresses(full_text, soup)

        return entities

    def _extract_emails(
        self, html: str, text: str, soup: BeautifulSoup
    ) -> list[str]:
        """Extract email addresses."""
        emails = set()

        # From mailto: links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if self._is_valid_email(email):
                    emails.add(email.lower())

        # From text content
        for match in self.EMAIL_PATTERN.finditer(text):
            email = match.group().lower()
            if self._is_valid_email(email):
                emails.add(email)

        # Try deobfuscated text
        deobfuscated = text
        for pattern, replacement in self.EMAIL_OBFUSCATION:
            deobfuscated = re.sub(
                pattern, replacement, deobfuscated, flags=re.I
            )
        for match in self.EMAIL_PATTERN.finditer(deobfuscated):
            email = match.group().lower()
            if self._is_valid_email(email):
                emails.add(email)

        return sorted(emails)

    def _extract_phones(self, text: str) -> list[str]:
        """Extract phone numbers."""
        phones = set()

        for pattern in self.PHONE_PATTERNS:
            for match in pattern.finditer(text):
                phone = match.group().strip()
                # Clean up
                phone = re.sub(r"[^\d+\-() ]", "", phone)
                if len(re.sub(r"\D", "", phone)) >= 7:
                    phones.add(phone)

        # Also check tel: links
        return sorted(phones)

    def _extract_social_links(
        self, soup: BeautifulSoup
    ) -> list[dict[str, str]]:
        """Extract social media links."""
        social = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith(("http://", "https://")):
                continue

            for platform, patterns in self.SOCIAL_PLATFORMS.items():
                for pattern in patterns:
                    if re.search(pattern, href, re.I):
                        if href not in seen_urls:
                            seen_urls.add(href)
                            social.append({
                                "platform": platform,
                                "url": href,
                            })
                        break

        return social

    def _extract_addresses(
        self, text: str, soup: BeautifulSoup
    ) -> list[str]:
        """Extract physical addresses (basic heuristic)."""
        addresses = []

        # Look for address tags
        for addr in soup.find_all("address"):
            addr_text = addr.get_text(strip=True)
            if addr_text and len(addr_text) > 10:
                addresses.append(addr_text)

        # Look for elements with address-related attributes
        address_selectors = [
            "[itemtype*='PostalAddress']",
            "[class*='address']",
            "[id*='address']",
        ]

        for selector in address_selectors:
            for elem in soup.select(selector):
                addr_text = elem.get_text(strip=True)
                if addr_text and len(addr_text) > 10 and addr_text not in addresses:
                    addresses.append(addr_text)

        return addresses[:10]  # Limit to avoid false positives

    def _is_valid_email(self, email: str) -> bool:
        """Validate email address."""
        if not email or "@" not in email:
            return False

        # Skip common false positives
        skip_domains = {
            "example.com", "test.com", "email.com",
            "domain.com", "sample.com",
        }
        domain = email.split("@")[-1].lower()
        if domain in skip_domains:
            return False

        # Skip image-like extensions
        if any(email.endswith(ext) for ext in [".png", ".jpg", ".gif", ".svg"]):
            return False

        return bool(self.EMAIL_PATTERN.match(email))