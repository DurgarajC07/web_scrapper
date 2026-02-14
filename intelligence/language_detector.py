"""
Language detection for web content.
"""

from __future__ import annotations

from bs4 import BeautifulSoup
from langdetect import detect, detect_langs, LangDetectException

from utils.logger import get_logger

logger = get_logger("language_detector")


class LanguageDetector:
    """Detects language of web content."""

    def detect(self, html: str, text: str = "") -> dict:
        """
        Detect language from HTML and text.
        
        Returns:
            dict with 'language', 'confidence', 'alternatives', 'source'
        """
        # Try HTML lang attribute first
        html_lang = self._extract_html_lang(html)
        if html_lang:
            return {
                "language": html_lang,
                "confidence": 1.0,
                "alternatives": [],
                "source": "html_attribute",
            }

        # Use text content for detection
        content = text if text else self._extract_text(html)
        
        if not content or len(content.strip()) < 20:
            return {
                "language": "unknown",
                "confidence": 0.0,
                "alternatives": [],
                "source": "insufficient_content",
            }

        try:
            # Detect with probabilities
            lang_probs = detect_langs(content)
            
            if not lang_probs:
                return {
                    "language": "unknown",
                    "confidence": 0.0,
                    "alternatives": [],
                    "source": "detection_failed",
                }

            primary = lang_probs[0]
            
            return {
                "language": primary.lang,
                "confidence": primary.prob,
                "alternatives": [
                    {"language": lp.lang, "confidence": lp.prob}
                    for lp in lang_probs[1:3]
                ],
                "source": "langdetect",
            }

        except LangDetectException as e:
            logger.warning("language_detection_failed", error=str(e))
            return {
                "language": "unknown",
                "confidence": 0.0,
                "alternatives": [],
                "source": "error",
            }

    def detect_multiple(self, html: str, text: str = "") -> list[dict]:
        """
        Detect if page contains multiple languages.
        
        Returns list of detected languages with confidence.
        """
        content = text if text else self._extract_text(html)
        
        if not content or len(content.strip()) < 20:
            return []

        try:
            lang_probs = detect_langs(content)
            return [
                {"language": lp.lang, "confidence": lp.prob}
                for lp in lang_probs
                if lp.prob > 0.1  # Only include if >10% confidence
            ]
        except LangDetectException:
            return []

    def _extract_html_lang(self, html: str) -> str:
        """Extract language from HTML lang attribute."""
        soup = BeautifulSoup(html, "lxml")
        
        # Check <html lang="...">
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang = html_tag["lang"].strip()
            # Normalize (e.g., "en-US" -> "en")
            return lang.split("-")[0].lower()

        # Check meta tag
        meta = soup.find("meta", attrs={"http-equiv": "content-language"})
        if meta and meta.get("content"):
            lang = meta["content"].strip()
            return lang.split("-")[0].lower()

        return ""

    def _extract_text(self, html: str) -> str:
        """Extract text content from HTML."""
        soup = BeautifulSoup(html, "lxml")
        
        # Remove script and style tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        return text
