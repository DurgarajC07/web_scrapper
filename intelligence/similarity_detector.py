"""
Similarity detection and duplicate content identification.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from simhash import Simhash

from utils.logger import get_logger

logger = get_logger("similarity_detector")


class SimilarityDetector:
    """Detects similar and duplicate content."""

    def __init__(self, threshold: float = 0.85):
        """
        Initialize similarity detector.
        
        Args:
            threshold: Similarity threshold (0-1) for considering content duplicate
        """
        self.threshold = threshold

    def compute_simhash(self, text: str) -> int:
        """
        Compute SimHash fingerprint for text.
        
        Returns:
            64-bit integer hash
        """
        if not text:
            return 0
        return Simhash(text).value

    def compute_content_hash(self, text: str) -> str:
        """
        Compute MD5 hash of content for exact duplicate detection.
        
        Returns:
            Hex string of MD5 hash
        """
        if not text:
            return ""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def is_duplicate(
        self, hash1: int, hash2: int, hamming_threshold: int = 3
    ) -> bool:
        """
        Check if two SimHash values represent duplicate content.
        
        Args:
            hash1: First SimHash value
            hash2: Second SimHash value
            hamming_threshold: Maximum Hamming distance for duplicates
            
        Returns:
            True if content is considered duplicate
        """
        if hash1 == 0 or hash2 == 0:
            return False
        
        # Calculate Hamming distance
        distance = bin(hash1 ^ hash2).count("1")
        return distance <= hamming_threshold

    def similarity_score(self, hash1: int, hash2: int) -> float:
        """
        Calculate similarity score between two SimHash values.
        
        Returns:
            Similarity score between 0 and 1
        """
        if hash1 == 0 or hash2 == 0:
            return 0.0
        
        # Calculate Hamming distance
        distance = bin(hash1 ^ hash2).count("1")
        
        # Convert to similarity (64 bits total)
        similarity = 1.0 - (distance / 64.0)
        return similarity

    def compute_url_similarity(self, url1: str, url2: str) -> float:
        """
        Calculate URL similarity score.
        
        Returns:
            Similarity score between 0 and 1
        """
        if not url1 or not url2:
            return 0.0

        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # Same URL
        if url1 == url2:
            return 1.0

        # Different domains
        if parsed1.netloc != parsed2.netloc:
            return 0.0

        # Same domain, compare paths
        path1 = parsed1.path.strip("/").split("/")
        path2 = parsed2.path.strip("/").split("/")

        if not path1 or not path2:
            return 0.5

        # Calculate path similarity
        common = sum(1 for a, b in zip(path1, path2) if a == b)
        max_len = max(len(path1), len(path2))
        
        return common / max_len if max_len > 0 else 0.0

    def fingerprint(self, text: str, url: str = "") -> dict:
        """
        Generate complete fingerprint for content.
        
        Returns:
            dict with simhash, content_hash, url
        """
        return {
            "simhash": self.compute_simhash(text),
            "content_hash": self.compute_content_hash(text),
            "url": url,
            "text_length": len(text),
        }

    def compare(self, fingerprint1: dict, fingerprint2: dict) -> dict:
        """
        Compare two fingerprints.
        
        Returns:
            dict with is_duplicate, similarity, url_similarity
        """
        simhash1 = fingerprint1.get("simhash", 0)
        simhash2 = fingerprint2.get("simhash", 0)
        
        content_similarity = self.similarity_score(simhash1, simhash2)
        is_dup = content_similarity >= self.threshold
        
        url_sim = 0.0
        if fingerprint1.get("url") and fingerprint2.get("url"):
            url_sim = self.compute_url_similarity(
                fingerprint1["url"], fingerprint2["url"]
            )

        # Exact match check
        exact_match = (
            fingerprint1.get("content_hash") == fingerprint2.get("content_hash")
            and fingerprint1.get("content_hash") != ""
        )

        return {
            "is_duplicate": is_dup or exact_match,
            "is_exact_match": exact_match,
            "content_similarity": content_similarity,
            "url_similarity": url_sim,
        }
