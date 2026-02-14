"""
Content type classification for web pages.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger("content_classifier")


class ContentClassifier:
    """Classifies web page content type using heuristics and signals."""

    # Signals for each content type
    CLASSIFICATION_SIGNALS = {
        "article": {
            "tags": ["article", "time", "byline"],
            "classes": [
                "article", "post", "blog", "story", "entry",
                "news", "editorial",
            ],
            "meta_types": ["article", "newsarticle", "blogposting"],
            "schemas": ["Article", "NewsArticle", "BlogPosting"],
        },
        "product": {
            "tags": [],
            "classes": [
                "product", "price", "add-to-cart", "buy",
                "shopping", "cart", "sku",
            ],
            "meta_types": ["product"],
            "schemas": ["Product", "Offer"],
        },
        "listing": {
            "tags": [],
            "classes": [
                "listing", "results", "grid", "catalog",
                "gallery", "directory",
            ],
            "meta_types": [],
            "schemas": ["ItemList", "CollectionPage"],
        },
        "forum": {
            "tags": [],
            "classes": [
                "forum", "thread", "reply", "comment",
                "discussion", "topic", "post-list",
            ],
            "meta_types": [],
            "schemas": ["DiscussionForumPosting"],
        },
        "homepage": {
            "tags": [],
            "classes": [
                "homepage", "home", "landing", "hero",
                "welcome", "main-page",
            ],
            "meta_types": ["website"],
            "schemas": ["WebSite"],
        },
        "contact": {
            "tags": ["address"],
            "classes": [
                "contact", "address", "phone", "email",
                "location", "map",
            ],
            "meta_types": ["contactpage"],
            "schemas": ["ContactPage"],
        },
        "about": {
            "tags": [],
            "classes": [
                "about", "bio", "team", "story",
                "mission", "history",
            ],
            "meta_types": ["aboutpage"],
            "schemas": ["AboutPage"],
        },
        "faq": {
            "tags": ["details", "summary"],
            "classes": [
                "faq", "question", "answer", "accordion",
                "help", "support",
            ],
            "meta_types": ["faqpage"],
            "schemas": ["FAQPage"],
        },
    }

    def classify(
        self, html: str, url: str = "", structured_data: list | None = None
    ) -> dict:
        """
        Classify page content type.
        Returns classification with confidence score.
        """
        soup = BeautifulSoup(html, "lxml")
        scores: dict[str, float] = Counter()

        # Signal-based scoring
        for content_type, signals in self.CLASSIFICATION_SIGNALS.items():
            score = 0.0

            # Check HTML tags
            for tag in signals["tags"]:
                if soup.find(tag):
                    score += 1.0

            # Check CSS classes and IDs
            html_lower = html.lower()
            for cls in signals["classes"]:
                # Count occurrences in class and id attributes
                if f'class="{cls}"' in html_lower or f"class='{cls}'" in html_lower:
                    score += 0.5
                if f'id="{cls}"' in html_lower or f"id='{cls}'" in html_lower:
                    score += 0.5
                # Also check for partial matches
                if cls in html_lower:
                    score += 0.2

            # Check meta types
            for meta_type in signals["meta_types"]:
                og_type = soup.find("meta", property="og:type")
                if og_type and og_type.get("content", "").lower() == meta_type:
                    score += 2.0

            # Check structured data schemas
            if structured_data:
                for item in structured_data:
                    item_type = item.get("@type", "")
                    if item_type in signals["schemas"]:
                        score += 2.0

            # URL-based signals
            if url:
                url_lower = url.lower()
                for cls in signals["classes"]:
                    if cls in url_lower:
                        score += 0.3

            scores[content_type] = score

        # Determine primary type
        if not scores:
            return {
                "type": "unknown",
                "confidence": 0.0,
                "scores": {},
            }

        # Get top classification
        sorted_types = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )
        primary_type, primary_score = sorted_types[0]

        # Calculate confidence (normalize to 0-1)
        max_possible_score = 10.0  # Rough estimate
        confidence = min(primary_score / max_possible_score, 1.0)

        # Require minimum score threshold
        if primary_score < 1.0:
            return {
                "type": "unknown",
                "confidence": confidence,
                "scores": dict(scores),
            }

        return {
            "type": primary_type,
            "confidence": confidence,
            "scores": dict(scores),
            "secondary_types": [
                {"type": t, "score": s}
                for t, s in sorted_types[1:3]
                if s > 0.5
            ],
        }