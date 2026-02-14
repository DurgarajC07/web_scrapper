"""
JSON file output for crawled data.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from utils.logger import get_logger

logger = get_logger("json_output")


class JSONOutput:
    """JSON file output handler for crawled pages."""

    def __init__(
        self,
        output_dir: str = "./output",
        pretty: bool = True,
        batch_size: int = 100,
    ):
        """
        Initialize JSON output.
        
        Args:
            output_dir: Directory for output files
            pretty: Pretty-print JSON
            batch_size: Number of pages per batch file
        """
        self.output_dir = Path(output_dir)
        self.pretty = pretty
        self.batch_size = batch_size
        self.current_batch: list[dict] = []
        self.batch_count = 0
        self.total_pages = 0

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def save_page(self, page_data: dict) -> None:
        """
        Save single page data.
        
        Args:
            page_data: Page data dictionary
        """
        # Add to current batch
        self.current_batch.append(page_data)
        self.total_pages += 1

        # Flush if batch is full
        if len(self.current_batch) >= self.batch_size:
            await self.flush()

    async def flush(self) -> None:
        """Write current batch to file."""
        if not self.current_batch:
            return

        self.batch_count += 1
        filename = self.output_dir / f"batch_{self.batch_count:04d}.json"

        # Prepare data
        data = {
            "batch": self.batch_count,
            "count": len(self.current_batch),
            "timestamp": datetime.utcnow().isoformat(),
            "pages": self.current_batch,
        }

        # Write to file
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            if self.pretty:
                json_str = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                json_str = json.dumps(data, ensure_ascii=False)
            await f.write(json_str)

        logger.info(
            "batch_written",
            batch=self.batch_count,
            count=len(self.current_batch),
            file=str(filename),
        )

        # Clear batch
        self.current_batch = []

    async def save_single(self, page_data: dict, filename: str | None = None) -> None:
        """
        Save single page to individual file.
        
        Args:
            page_data: Page data dictionary
            filename: Optional custom filename
        """
        if not filename:
            # Generate filename from URL or timestamp
            url = page_data.get("url", "")
            if url:
                # Use URL hash as filename
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                filename = f"page_{url_hash}.json"
            else:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"page_{timestamp}.json"

        filepath = self.output_dir / filename

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            if self.pretty:
                json_str = json.dumps(page_data, indent=2, ensure_ascii=False)
            else:
                json_str = json.dumps(page_data, ensure_ascii=False)
            await f.write(json_str)

        logger.debug("page_written", file=str(filepath))

    async def save_summary(self, summary_data: dict) -> None:
        """
        Save crawl summary.
        
        Args:
            summary_data: Summary statistics
        """
        filename = self.output_dir / "summary.json"

        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            json_str = json.dumps(summary_data, indent=2, ensure_ascii=False)
            await f.write(json_str)

        logger.info("summary_written", file=str(filename))

    def get_stats(self) -> dict:
        """Get output statistics."""
        return {
            "total_pages": self.total_pages,
            "batches_written": self.batch_count,
            "current_batch_size": len(self.current_batch),
            "output_dir": str(self.output_dir),
        }

    async def close(self) -> None:
        """Flush remaining data and close."""
        await self.flush()
        logger.info("json_output_closed", stats=self.get_stats())
