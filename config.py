"""
Global configuration management for IAWIC.
Supports environment variables, .env files, and programmatic overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class CrawlStrategy(str, Enum):
    BFS = "bfs"
    DFS = "dfs"
    HYBRID = "hybrid"


class RenderMode(str, Enum):
    STATIC = "static"
    JAVASCRIPT = "javascript"
    AUTO = "auto"


@dataclass
class CrawlConfig:
    """Main crawl configuration."""

    # Target
    url: str = ""
    crawl_depth: int = 3
    max_pages: int = 1000
    follow_external_links: bool = False
    include_subdomains: bool = True

    # Strategy
    strategy: CrawlStrategy = CrawlStrategy.HYBRID
    render_mode: RenderMode = RenderMode.AUTO

    # Rate Limiting
    requests_per_second: float = 2.0
    min_delay: float = 0.5
    max_delay: float = 3.0
    adaptive_delay: bool = True

    # Timeouts
    page_timeout: int = 30
    network_timeout: int = 60
    render_timeout: int = 15

    # Content
    extract_images: bool = True
    extract_videos: bool = True
    extract_files: bool = True
    extract_entities: bool = True
    extract_structured_data: bool = True
    extract_text_content: bool = True
    store_html: bool = False

    # Deduplication
    enable_dedup: bool = True
    similarity_threshold: float = 0.85

    # Anti-blocking
    rotate_user_agents: bool = True
    use_proxies: bool = False
    respect_robots_txt: bool = True

    # Output
    output_dir: str = "./output"
    output_format: str = "json"

    # Intelligence
    enable_classification: bool = True
    enable_summarization: bool = False
    enable_content_cleaning: bool = True
    enable_language_detection: bool = True


@dataclass
class StorageConfig:
    """Storage backend configuration."""

    # MongoDB
    mongo_enabled: bool = False
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db: str = os.getenv("MONGO_DB", "iawic")

    # Elasticsearch
    elastic_enabled: bool = False
    elastic_uri: str = os.getenv("ELASTIC_URI", "http://localhost:9200")
    elastic_index: str = os.getenv("ELASTIC_INDEX", "iawic_pages")

    # Redis
    redis_enabled: bool = False
    redis_uri: str = os.getenv("REDIS_URI", "redis://localhost:6379")


@dataclass
class ProxyConfig:
    """Proxy pool configuration."""

    proxies: list[str] = field(default_factory=list)
    rotation_strategy: str = "round_robin"  # round_robin | random | least_used
    health_check_interval: int = 300
    max_failures: int = 3


@dataclass
class IAWICConfig:
    """Top-level configuration container."""

    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    workers: int = int(os.getenv("WORKERS", "4"))

    @classmethod
    def from_dict(cls, data: dict) -> IAWICConfig:
        config = cls()
        crawl_data = data.get("crawl", {})
        for key, value in crawl_data.items():
            if hasattr(config.crawl, key):
                setattr(config.crawl, key, value)

        storage_data = data.get("storage", {})
        for key, value in storage_data.items():
            if hasattr(config.storage, key):
                setattr(config.storage, key, value)

        proxy_data = data.get("proxy", {})
        for key, value in proxy_data.items():
            if hasattr(config.proxy, key):
                setattr(config.proxy, key, value)

        if "log_level" in data:
            config.log_level = data["log_level"]
        if "workers" in data:
            config.workers = data["workers"]

        return config