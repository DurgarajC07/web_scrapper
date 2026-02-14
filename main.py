"""
IAWIC - Intelligent Adaptive Web Intelligence Crawler
Main entry point and CLI interface.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from config import IAWICConfig
from core.crawler_engine import CrawlerEngine
from storage.elastic_storage import ElasticStorage
from storage.json_output import JSONOutput
from storage.mongo_storage import MongoStorage
from utils.logger import get_logger, setup_logging

logger = get_logger("main")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="IAWIC - Intelligent Adaptive Web Intelligence Crawler"
    )
    parser.add_argument("url", help="Starting URL to crawl")
    parser.add_argument(
        "--config",
        help="Path to configuration JSON file",
        default=None,
    )
    parser.add_argument(
        "--depth",
        type=int,
        help="Maximum crawl depth",
        default=3,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages to crawl",
        default=1000,
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for JSON files",
        default="./output",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of concurrent workers",
        default=4,
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    parser.add_argument(
        "--mongo",
        action="store_true",
        help="Enable MongoDB storage",
    )
    parser.add_argument(
        "--elastic",
        action="store_true",
        help="Enable Elasticsearch storage",
    )
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        default=True,
        help="Respect robots.txt",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Load configuration
    if args.config:
        with open(args.config) as f:
            config_dict = json.load(f)
        config = IAWICConfig.from_dict(config_dict)
    else:
        config = IAWICConfig()

    # Override with CLI arguments
    config.crawl.crawl_depth = args.depth
    config.crawl.max_pages = args.max_pages
    config.crawl.output_dir = args.output_dir
    config.crawl.respect_robots_txt = args.respect_robots
    config.workers = args.workers
    config.log_level = args.log_level

    # Storage configuration
    config.storage.mongo_enabled = args.mongo
    config.storage.elastic_enabled = args.elastic

    logger.info("iawic_starting", url=args.url, config=vars(args))

    # Initialize storage backends
    storage_backends = []

    # JSON output (always enabled)
    json_output = JSONOutput(output_dir=args.output_dir)
    storage_backends.append(json_output)

    # MongoDB
    mongo_storage = None
    if config.storage.mongo_enabled:
        mongo_storage = MongoStorage(
            uri=config.storage.mongo_uri,
            database=config.storage.mongo_db,
        )
        await mongo_storage.connect()
        storage_backends.append(mongo_storage)

    # Elasticsearch
    elastic_storage = None
    if config.storage.elastic_enabled:
        elastic_storage = ElasticStorage(
            uri=config.storage.elastic_uri,
            index=config.storage.elastic_index,
        )
        await elastic_storage.connect()
        storage_backends.append(elastic_storage)

    # Create crawler engine
    crawler = CrawlerEngine(config)

    # Store pages hook (simplified - in production would be event-based)
    original_extract = crawler._extract_page_data

    async def extract_and_store(url, html, depth):
        page_data = await original_extract(url, html, depth)
        
        # Save to all storage backends
        for backend in storage_backends:
            try:
                await backend.save_page(page_data)
            except Exception as e:
                logger.error(
                    "storage_failed",
                    backend=type(backend).__name__,
                    error=str(e),
                )
        
        return page_data

    crawler._extract_page_data = extract_and_store

    try:
        # Start crawling
        await crawler.start(args.url)

        # Get final statistics
        stats = crawler.get_stats()
        logger.info("crawl_completed", stats=stats)

        # Convert datetime objects to strings for JSON serialization
        stats_for_json = stats.copy()
        if stats_for_json.get("start_time"):
            stats_for_json["start_time"] = stats_for_json["start_time"].isoformat()
        if stats_for_json.get("end_time"):
            stats_for_json["end_time"] = stats_for_json["end_time"].isoformat()

        # Save summary
        await json_output.save_summary(stats_for_json)

    except KeyboardInterrupt:
        logger.info("crawl_interrupted")
        await crawler.stop()

    except Exception as e:
        logger.error("crawl_failed", error=str(e))
        sys.exit(1)

    finally:
        # Cleanup storage backends
        await json_output.close()

        if mongo_storage:
            await mongo_storage.disconnect()

        if elastic_storage:
            await elastic_storage.disconnect()

    logger.info("iawic_finished")


if __name__ == "__main__":
    asyncio.run(main())
