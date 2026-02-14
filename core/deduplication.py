"""
Content deduplication using multiple strategies.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.hash_utils import SimHash, content_hash, md5_hash
from utils.logger import get_logger

logger = get_logger("deduplication")


@dataclass
class DeduplicationResult:
    is_duplicate: bool
    similarity: float
    matching_url: str | None
    method: str


class ContentDeduplicator:
    """
    Multi-strategy content deduplication engine.
    Uses both exact hash matching and SimHash for near-duplicates.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self._threshold = similarity_threshold
        self._exact_hashes: dict[str, str] = {}  # hash -> url
        self._simhashes: dict[str, int] = {}  # url -> simhash
        self._simhasher = SimHash(hash_bits=64)
        self._duplicate_count = 0

    def check(self, url: str, text_content: str) -> DeduplicationResult:
        """Check if content is duplicate of previously seen content."""
        if not text_content or len(text_content.strip()) < 50:
            return DeduplicationResult(
                is_duplicate=False,
                similarity=0.0,
                matching_url=None,
                method="skipped_short_content",
            )

        # Strategy 1: Exact match
        exact = self._check_exact(url, text_content)
        if exact.is_duplicate:
            return exact

        # Strategy 2: Near-duplicate with SimHash
        near = self._check_simhash(url, text_content)
        if near.is_duplicate:
            return near

        # Not a duplicate — store for future checks
        self._store(url, text_content)

        return DeduplicationResult(
            is_duplicate=False,
            similarity=0.0,
            matching_url=None,
            method="unique",
        )

    def _check_exact(self, url: str, text: str) -> DeduplicationResult:
        """Check for exact content match."""
        h = content_hash(text)
        if h in self._exact_hashes:
            self._duplicate_count += 1
            matching_url = self._exact_hashes[h]
            logger.info(
                "exact_duplicate_found",
                url=url,
                matching_url=matching_url,
            )
            return DeduplicationResult(
                is_duplicate=True,
                similarity=1.0,
                matching_url=matching_url,
                method="exact_hash",
            )
        return DeduplicationResult(
            is_duplicate=False,
            similarity=0.0,
            matching_url=None,
            method="exact_hash",
        )

    def _check_simhash(self, url: str, text: str) -> DeduplicationResult:
        """Check for near-duplicate using SimHash."""
        current_hash = self._simhasher.compute(text)

        best_similarity = 0.0
        best_url = None

        for stored_url, stored_hash in self._simhashes.items():
            similarity = self._simhasher.similarity(current_hash, stored_hash)
            if similarity > best_similarity:
                best_similarity = similarity
                best_url = stored_url

        if best_similarity >= self._threshold:
            self._duplicate_count += 1
            logger.info(
                "near_duplicate_found",
                url=url,
                matching_url=best_url,
                similarity=f"{best_similarity:.3f}",
            )
            return DeduplicationResult(
                is_duplicate=True,
                similarity=best_similarity,
                matching_url=best_url,
                method="simhash",
            )

        return DeduplicationResult(
            is_duplicate=False,
            similarity=best_similarity,
            matching_url=best_url,
            method="simhash",
        )

    def _store(self, url: str, text: str):
        """Store content fingerprints for future comparison."""
        self._exact_hashes[content_hash(text)] = url
        self._simhashes[url] = self._simhasher.compute(text)

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count

    def get_stats(self) -> dict:
        return {
            "total_unique": len(self._exact_hashes),
            "total_duplicates": self._duplicate_count,
            "similarity_threshold": self._threshold,
        }