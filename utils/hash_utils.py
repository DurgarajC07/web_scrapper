"""
Hashing utilities for content fingerprinting and deduplication.
"""

import hashlib
import re
from typing import Any


def md5_hash(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.md5(content).hexdigest()


def sha256_hash(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def content_hash(text: str) -> str:
    """Generate a normalized hash of text content for deduplication."""
    # Normalize whitespace and case
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return sha256_hash(normalized)


def url_hash(url: str) -> str:
    """Generate hash of normalized URL."""
    return md5_hash(url.lower().strip())


class SimHash:
    """
    SimHash implementation for near-duplicate detection.
    Produces a 64-bit fingerprint that preserves similarity.
    """

    def __init__(self, hash_bits: int = 64):
        self.hash_bits = hash_bits

    def _string_hash(self, token: str) -> int:
        """Hash a single token to hash_bits integer."""
        raw = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(raw, 16) % (2**self.hash_bits)

    def compute(self, text: str) -> int:
        """Compute SimHash fingerprint for text."""
        tokens = self._tokenize(text)
        if not tokens:
            return 0

        # Initialize vector
        v = [0] * self.hash_bits

        for token in tokens:
            token_hash = self._string_hash(token)
            for i in range(self.hash_bits):
                bit = (token_hash >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1

        # Build fingerprint
        fingerprint = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                fingerprint |= 1 << i

        return fingerprint

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into shingles."""
        words = re.findall(r"\w+", text.lower())
        # Create 3-word shingles
        shingles = []
        for i in range(max(1, len(words) - 2)):
            shingle = " ".join(words[i : i + 3])
            shingles.append(shingle)
        return shingles

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """Calculate Hamming distance between two SimHash values."""
        xor = hash1 ^ hash2
        distance = 0
        while xor:
            distance += 1
            xor &= xor - 1
        return distance

    def similarity(self, hash1: int, hash2: int) -> float:
        """Calculate similarity score (0.0 to 1.0)."""
        distance = self.hamming_distance(hash1, hash2)
        return 1.0 - (distance / self.hash_bits)