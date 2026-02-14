"""
Structured data extraction: JSON-LD, Microdata, RDFa.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger("structured_data_extractor")


@dataclass
class StructuredDataItem:
    """Single structured data item."""
    format: str  # json-ld, microdata, rdfa
    type: str  # Schema.org type
    data: dict
    raw: str = ""


class StructuredDataExtractor:
    """Extracts structured data from HTML pages."""

    def extract(self, html: str) -> list[dict]:
        """Extract all structured data from HTML."""
        results = []

        # JSON-LD
        results.extend(self._extract_json_ld(html))

        # Microdata (using extruct if available)
        results.extend(self._extract_microdata(html))

        # RDFa
        results.extend(self._extract_rdfa(html))

        return results

    def _extract_json_ld(self, html: str) -> list[dict]:
        """Extract JSON-LD structured data."""
        results = []
        soup = BeautifulSoup(html, "lxml")

        for script in soup.find_all(
            "script", attrs={"type": "application/ld+json"}
        ):
            try:
                text = script.string
                if not text:
                    continue

                # Clean potential issues
                text = text.strip()

                data = json.loads(text)

                # Handle arrays
                if isinstance(data, list):
                    for item in data:
                        results.append({
                            "format": "json-ld",
                            "type": item.get("@type", "Unknown"),
                            "data": item,
                        })
                elif isinstance(data, dict):
                    results.append({
                        "format": "json-ld",
                        "type": data.get("@type", "Unknown"),
                        "data": data,
                    })

            except json.JSONDecodeError as e:
                logger.debug("json_ld_parse_error", error=str(e))
            except Exception as e:
                logger.debug("json_ld_extraction_error", error=str(e))

        return results

    def _extract_microdata(self, html: str) -> list[dict]:
        """Extract Microdata using extruct library."""
        try:
            import extruct

            data = extruct.extract(
                html,
                syntaxes=["microdata"],
                uniform=True,
            )

            results = []
            for item in data.get("microdata", []):
                results.append({
                    "format": "microdata",
                    "type": item.get("@type", "Unknown"),
                    "data": item,
                })
            return results

        except ImportError:
            # Fallback: basic microdata extraction
            return self._extract_microdata_manual(html)
        except Exception as e:
            logger.debug("microdata_extraction_error", error=str(e))
            return []

    def _extract_microdata_manual(self, html: str) -> list[dict]:
        """Basic microdata extraction without extruct."""
        results = []
        soup = BeautifulSoup(html, "lxml")

        for item in soup.find_all(attrs={"itemscope": True}):
            item_type = item.get("itemtype", "")
            properties = {}

            for prop in item.find_all(attrs={"itemprop": True}):
                name = prop.get("itemprop", "")
                # Get value from appropriate attribute
                if prop.name == "meta":
                    value = prop.get("content", "")
                elif prop.name in ("a", "link"):
                    value = prop.get("href", "")
                elif prop.name == "img":
                    value = prop.get("src", "")
                elif prop.name == "time":
                    value = prop.get("datetime", prop.get_text(strip=True))
                else:
                    value = prop.get_text(strip=True)

                if name and value:
                    properties[name] = value

            if properties:
                results.append({
                    "format": "microdata",
                    "type": item_type.split("/")[-1] if item_type else "Unknown",
                    "data": {
                        "@type": item_type,
                        **properties,
                    },
                })

        return results

    def _extract_rdfa(self, html: str) -> list[dict]:
        """Extract RDFa structured data."""
        try:
            import extruct

            data = extruct.extract(
                html,
                syntaxes=["rdfa"],
                uniform=True,
            )

            results = []
            for item in data.get("rdfa", []):
                results.append({
                    "format": "rdfa",
                    "type": item.get("@type", ["Unknown"])[0]
                    if isinstance(item.get("@type"), list)
                    else item.get("@type", "Unknown"),
                    "data": item,
                })
            return results

        except ImportError:
            return []
        except Exception as e:
            logger.debug("rdfa_extraction_error", error=str(e))
            return []