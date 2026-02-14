"""
Content summarization using extractive methods.
"""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger("summarizer")


class Summarizer:
    """Generates summaries of web content."""

    def __init__(self, max_sentences: int = 3):
        """
        Initialize summarizer.
        
        Args:
            max_sentences: Maximum number of sentences in summary
        """
        self.max_sentences = max_sentences

    def summarize(self, text: str, html: str = "") -> dict:
        """
        Generate extractive summary of content.
        
        Returns:
            dict with 'summary', 'sentences', 'method'
        """
        if not text or len(text.strip()) < 50:
            return {
                "summary": text.strip(),
                "sentences": [text.strip()] if text.strip() else [],
                "method": "too_short",
            }

        # Try extractive summarization
        sentences = self._extract_sentences(text)
        
        if len(sentences) <= self.max_sentences:
            return {
                "summary": " ".join(sentences),
                "sentences": sentences,
                "method": "full_text",
            }

        # Score and rank sentences
        scored = self._score_sentences(sentences, text)
        
        # Get top sentences
        top_sentences = sorted(
            scored, key=lambda x: x[1], reverse=True
        )[:self.max_sentences]
        
        # Sort by original order
        top_sentences.sort(key=lambda x: x[2])
        
        summary_sentences = [s[0] for s in top_sentences]
        
        return {
            "summary": " ".join(summary_sentences),
            "sentences": summary_sentences,
            "method": "extractive",
        }

    def summarize_html(self, html: str) -> dict:
        """
        Generate summary from HTML, using structure hints.
        
        Returns:
            dict with summary information
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Try to get first paragraph
        first_p = soup.find("p")
        if first_p:
            text = first_p.get_text(strip=True)
            if len(text) > 50:
                return {
                    "summary": text[:500],
                    "sentences": [text[:500]],
                    "method": "first_paragraph",
                }

        # Fallback to full text extraction
        full_text = soup.get_text(separator=" ", strip=True)
        return self.summarize(full_text)

    def _extract_sentences(self, text: str) -> list[str]:
        """Extract sentences from text."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Clean and filter
        cleaned = []
        for sent in sentences:
            sent = sent.strip()
            # Filter out very short sentences
            if len(sent) > 20:
                cleaned.append(sent)
        
        return cleaned

    def _score_sentences(
        self, sentences: list[str], full_text: str
    ) -> list[tuple[str, float, int]]:
        """
        Score sentences for importance.
        
        Returns:
            List of (sentence, score, original_index) tuples
        """
        # Calculate word frequencies
        words = re.findall(r'\b\w+\b', full_text.lower())
        word_freq = Counter(words)
        
        # Remove very common words (simple stopwords)
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at",
            "to", "for", "of", "with", "by", "from", "as", "is", "was",
            "are", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "should", "could",
            "may", "might", "must", "can", "this", "that", "these",
            "those", "i", "you", "he", "she", "it", "we", "they",
        }
        
        for word in stopwords:
            word_freq.pop(word, None)

        # Score sentences
        scored = []
        for idx, sent in enumerate(sentences):
            score = 0.0
            sent_words = re.findall(r'\b\w+\b', sent.lower())
            
            # Sum word frequencies
            for word in sent_words:
                score += word_freq.get(word, 0)
            
            # Normalize by sentence length
            if len(sent_words) > 0:
                score /= len(sent_words)
            
            # Boost first few sentences slightly
            if idx < 3:
                score *= 1.2
            
            scored.append((sent, score, idx))
        
        return scored

    def truncate(self, text: str, max_length: int = 200) -> str:
        """
        Simple truncation with word boundary respect.
        
        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        
        # Find last space before max_length
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")
        
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + "..."
