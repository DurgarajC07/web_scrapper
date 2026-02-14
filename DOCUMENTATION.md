# IAWIC - Intelligent Adaptive Web Intelligence Crawler

## Complete Technical Documentation

### Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Extraction System](#extraction-system)
- [Intelligence Layer](#intelligence-layer)
- [Rendering Engines](#rendering-engines)
- [Storage Backends](#storage-backends)
- [Utilities](#utilities)
- [Configuration](#configuration)
- [Data Flow](#data-flow)
- [Usage Guide](#usage-guide)
- [Advanced Features](#advanced-features)

---

## Overview

**IAWIC** (Intelligent Adaptive Web Intelligence Crawler) is an advanced, production-grade web crawler built with Python and async/await patterns. It's designed to intelligently crawl websites while respecting robots.txt, avoiding duplicate content, and extracting rich structured data from web pages.

### Key Features

- **Async Architecture**: Built on asyncio for high-performance concurrent crawling
- **Intelligent Rate Limiting**: Adaptive per-domain rate limiting that adjusts based on server responses
- **Multiple Rendering Modes**: Supports both static HTML fetching and JavaScript rendering (via Playwright)
- **Content Deduplication**: Uses SimHash and exact hash matching to identify duplicate content
- **Rich Data Extraction**: Extracts metadata, links, entities (emails, phones, addresses), media, and structured data
- **Content Intelligence**: Language detection, content classification, and similarity detection
- **Flexible Storage**: JSON files, MongoDB, Elasticsearch, and Redis support
- **Robots.txt Compliance**: Full support for robots.txt parsing including crawl-delay directives
- **Anti-Blocking**: User-agent rotation, proxy support, and blocking detection
- **Priority Queue**: BFS/DFS hybrid frontier with intelligent URL prioritization

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Main Entry (main.py)                     │
│                  CLI Interface & Configuration                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CrawlerEngine (core)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  URL Frontier   │  Rate Limiter  │  Robots Parser       │  │
│  │  URL Normalizer │  Session Mgr   │  Deduplication       │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────┬──────────────────────────┘
               │                      │
       ┌───────┴────────┐     ┌──────┴──────────┐
       ▼                ▼     ▼                  ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
│  Rendering  │  │  Extraction  │  │  Intelligence   │
│             │  │              │  │                 │
│ Static      │  │ Content      │  │ Content Cleaner │
│ Playwright  │  │ Metadata     │  │ Language Detect │
│ Scroll      │  │ Links        │  │ Similarity      │
│             │  │ Entities     │  │ Classification  │
│             │  │ Media        │  │                 │
└─────────────┘  └──────────────┘  └─────────────────┘
       │                │                    │
       └────────────────┴────────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Storage Backends     │
           │                        │
           │  JSON | MongoDB |      │
           │  Elasticsearch         │
           └────────────────────────┘
```

### Component Interaction

1. **CrawlerEngine** orchestrates all components
2. **URLFrontier** manages the queue of URLs to crawl
3. **RateLimiter** controls request frequency per domain
4. **Fetchers/Renderers** retrieve page content (static or JS-rendered)
5. **Extractors** parse and extract various data types
6. **Intelligence** layer processes and classifies content
7. **Storage** backends persist the extracted data

---

## Core Components

### 1. CrawlerEngine (`core/crawler_engine.py`)

The central orchestrator that coordinates all crawling activities.

**Responsibilities:**
- Manage worker tasks for concurrent crawling
- Coordinate URL fetching and data extraction
- Handle errors and retry logic
- Collect and report statistics

**Key Methods:**
- `start(seed_url)`: Start crawling from a seed URL
- `stop()`: Gracefully stop the crawler
- `_worker(worker_id)`: Worker task that processes URLs from the frontier
- `_crawl_page(url, depth)`: Crawl a single page
- `_extract_page_data(url, html, depth)`: Extract all data from a page

**Configuration:**
```python
config = IAWICConfig()
config.crawl.crawl_depth = 3
config.crawl.max_pages = 1000
config.workers = 4

crawler = CrawlerEngine(config)
await crawler.start("https://example.com")
```

### 2. URL Frontier (`core/url_frontier.py`)

A priority-based queue system for managing URLs to be crawled.

**Features:**
- Priority levels: CRITICAL, HIGH, NORMAL, LOW, DEFERRED
- Automatic deduplication using URL hashes
- Depth tracking to respect crawl depth limits
- Statistics tracking (added, crawled, duplicates)

**Priority Queue:**
Uses Python's heapq for efficient priority queue operations. URLs are ordered by:
1. Priority level (0-4)
2. Insertion order (FIFO within same priority)

**Key Methods:**
- `add(url, depth, priority, parent_url)`: Add URL to frontier
- `get(timeout)`: Get next URL to crawl
- `mark_crawled(url)`: Mark URL as successfully crawled
- `mark_failed(url)`: Mark URL as failed (with retry logic)

**Data Structure:**
```python
@dataclass
class URLEntry:
    priority: int           # 0-4 (CRITICAL to DEFERRED)
    depth: int             # Current depth in crawl tree
    url: str               # Normalized URL
    parent_url: str        # URL that linked to this
    discovered_at: float   # Timestamp
    retry_count: int       # Number of failed attempts
    metadata: dict         # Additional metadata
```

### 3. Rate Limiter (`core/rate_limiter.py`)

Adaptive per-domain rate limiting system.

**Features:**
- Per-domain rate limiting
- Adaptive delays based on server responses
- Handles 429 (Too Many Requests) and 5xx errors
- Respects robots.txt crawl-delay directives
- Jitter to avoid synchronized requests

**Adaptation Logic:**
```python
# Increases delay on:
- 429 status: delay *= 3
- 5xx errors: delay *= 2
- 3+ consecutive errors: delay *= 2

# Decreases delay on:
- Successful requests: delay *= 0.95
- Bounded by min_delay and max_delay
```

**State Tracking:**
```python
@dataclass
class DomainState:
    last_request_time: float
    request_count: int
    error_count: int
    consecutive_errors: int
    avg_response_time: float
    current_delay: float
```

### 4. Robots.txt Parser (`core/robots_parser.py`)

Parses and respects robots.txt rules.

**Features:**
- Async robots.txt fetching
- Parsing of robots.txt directives
- Sitemap extraction
- Crawl-delay extraction
- Per-domain caching (TTL: 1 hour)
- Fallback on 404 (allows all)

**Extracted Information:**
- Allowed/disallowed paths
- Crawl-delay directive
- Sitemap URLs
- User-agent specific rules

### 5. URL Normalizer (`core/url_normalizer.py`)

Ensures consistent URL representation across the crawler.

**Normalization Steps:**
1. Resolve relative URLs
2. Normalize scheme (http/https)
3. Normalize host (lowercase, remove trailing dots)
4. Remove default ports (80, 443)
5. Normalize path (resolve . and .., remove duplicate slashes)
6. Remove tracking parameters (utm_*, fbclid, etc.)
7. Sort query parameters
8. Remove fragments (optional)

**Example:**
```python
# Input:
"HTTP://Example.COM:80/Path//To/./Page?utm_source=google&id=123#section"

# Output:
"http://example.com/path/to/page?id=123"
```

### 6. Content Deduplicator (`core/deduplication.py`)

Multi-strategy deduplication engine.

**Strategy 1: Exact Hash**
- SHA-256 hash of normalized text content
- Fast, deterministic matching
- 100% precision for exact duplicates

**Strategy 2: SimHash**
- 64-bit locality-sensitive hash
- Detects near-duplicates (>85% similarity threshold)
- Uses 3-word shingles for fingerprinting
- Hamming distance for comparison

**Workflow:**
```
Text Content
     ↓
Normalize (lowercase, whitespace)
     ↓
Exact Hash Check → If match: Duplicate
     ↓
SimHash Compute
     ↓
Compare with all stored SimHashes
     ↓
If similarity > threshold: Near-Duplicate
     ↓
Store fingerprints for future comparison
```

### 7. Session Manager (`core/session_manager.py`)

Manages HTTP sessions, cookies, and authentication.

**Features:**
- Cookie management (from file or dict)
- Basic authentication
- Bearer token authentication
- Custom headers
- Integration with httpx and Playwright

**Use Cases:**
- Crawling authenticated areas
- Maintaining session state
- Custom API authentication

---

## Extraction System

### 1. Content Extractor (`extraction/content_extractor.py`)

Classifies page content type using heuristic analysis.

**Content Types Detected:**
- **Article**: Blog posts, news articles
- **Product**: E-commerce product pages
- **Listing**: Category pages, search results
- **Forum**: Discussion threads
- **Homepage**: Main landing pages
- **Contact**: Contact information pages
- **About**: About us pages
- **FAQ**: Frequently asked questions

**Classification Signals:**
- HTML tags (article, time, address, etc.)
- CSS classes and IDs
- Meta tags (og:type)
- Structured data schemas
- URL patterns

**Output:**
```python
{
    "type": "article",
    "confidence": 0.85,
    "scores": {
        "article": 8.5,
        "blog": 3.2,
        "product": 0.5
    },
    "secondary_types": [
        {"type": "blog", "score": 3.2}
    ]
}
```

### 2. Link Extractor (`extraction/link_extractor.py`)

Extracts and classifies links from HTML.

**Features:**
- Finds all `<a href>` links
- Skips JavaScript, mailto, tel links
- Normalizes URLs
- Classifies as internal/external
- Extracts link text, title, rel attributes
- Detects nofollow links

**Link Classification:**
```python
# Internal links: Same domain (+ subdomains if configured)
# External links: Different domains
```

**Output:**
```python
{
    "internal": ["https://example.com/page1", ...],
    "external": ["https://other.com/page", ...],
    "all_links": [
        {
            "url": "https://example.com/page1",
            "text": "Click here",
            "title": "Page title",
            "rel": [],
            "is_nofollow": False,
            "is_internal": True
        }
    ]
}
```

### 3. Metadata Extractor (`extraction/metadata_extractor.py`)

Extracts comprehensive page metadata.

**Extracted Fields:**
- **Title**: `<title>`, og:title, or first `<h1>`
- **Description**: Meta description
- **Canonical URL**: `<link rel="canonical">`
- **Language**: HTML lang attribute or meta tag
- **Author**: Meta author tag
- **Keywords**: Meta keywords tag
- **Charset**: Character encoding
- **Favicon**: Icon URLs
- **OpenGraph**: All og:* meta tags
- **Twitter Cards**: All twitter:* meta tags
- **Other Meta**: Additional meta tags

**OpenGraph Example:**
```python
{
    "og": {
        "type": "article",
        "title": "Article Title",
        "description": "Article description",
        "image": "https://example.com/image.jpg",
        "url": "https://example.com/article"
    }
}
```

### 4. Entity Extractor (`extraction/entity_extractor.py`)

Extracts structured entities from pages.

**Entity Types:**

**Emails:**
- From mailto: links
- Regex pattern matching
- Deobfuscation (converts "[at]" to "@", "[dot]" to ".")
- Validation and filtering

**Phones:**
- Multiple format support (US, UK, international)
- Regex pattern matching
- tel: link extraction

**Social Media Links:**
- Twitter/X, Facebook, Instagram, LinkedIn
- YouTube, GitHub, TikTok, Pinterest, Reddit
- Platform identification

**Addresses:**
- `<address>` tag content
- Elements with address-related attributes
- Microdata/schema detection

**Output:**
```python
{
    "emails": ["contact@example.com"],
    "phones": ["+1-555-0123"],
    "addresses": ["123 Main St, City, State 12345"],
    "social_links": [
        {"platform": "twitter", "url": "https://twitter.com/username"}
    ]
}
```

### 5. Media Extractor (`extraction/media_extractor.py`)

Extracts images, videos, and downloadable files.

**Images:**
- `<img>` tags (including lazy-loaded)
- `<picture>` and `<source>` elements
- Background images from inline styles
- Srcset handling
- Alt text, title, dimensions

**Videos:**
- HTML5 `<video>` elements
- YouTube, Vimeo, Dailymotion embed detection
- Iframe and embed tags
- Poster images

**Files:**
- Links to downloadable files (PDF, DOC, ZIP, etc.)
- File type detection
- Filename extraction

**Output:**
```python
{
    "images": [
        {
            "url": "https://example.com/image.jpg",
            "alt": "Image description",
            "width": 1920,
            "height": 1080,
            "format": "JPEG"
        }
    ],
    "videos": [
        {
            "url": "https://youtube.com/embed/...",
            "type": "iframe",
            "source": "youtube",
            "title": "Video title"
        }
    ],
    "files": [
        {
            "url": "https://example.com/doc.pdf",
            "file_type": "PDF Document",
            "filename": "doc.pdf"
        }
    ]
}
```

### 6. Structured Data Extractor (`extraction/structured_data_extractor.py`)

Extracts structured data from pages (JSON-LD, Microdata, RDFa).

**Formats Supported:**
- JSON-LD
- Microdata
- RDFa
- Microformats

**Uses extruct library for parsing.**

---

## Intelligence Layer

### 1. Content Cleaner (`intelligence/content_cleaner.py`)

Cleans HTML and extracts main content.

**Cleaning Steps:**
1. Remove NULL bytes and control characters
2. Remove `<script>`, `<style>`, `<noscript>` tags
3. Remove HTML comments
4. Remove boilerplate (nav, footer, ads, sidebars)
5. Extract main content using readability-lxml
6. Clean attributes (keep only href, src, alt, title)
7. Normalize whitespace

**Output:**
```python
{
    "cleaned_html": "<html>...</html>",
    "main_content": "<article>...</article>",
    "text": "Clean text content..."
}
```

**Boilerplate Removal:**
Removes common boilerplate selectors:
- nav, header, footer, aside
- .navigation, .menu, .sidebar
- .advertisement, .ad
- .social, .share, .comments

### 2. Language Detector (`intelligence/language_detector.py`)

Detects the language of web content.

**Detection Methods:**
1. **HTML lang attribute** (highest priority)
2. **Meta content-language tag**
3. **Text analysis** using langdetect library

**Features:**
- Returns primary language with confidence score
- Provides alternative language candidates
- Handles multi-language content
- Minimum content threshold (20 characters)

**Output:**
```python
{
    "language": "en",
    "confidence": 0.99,
    "alternatives": [
        {"language": "es", "confidence": 0.45}
    ],
    "source": "langdetect"  # or "html_attribute"
}
```

**Supported Languages:**
All languages supported by langdetect (50+ languages).

### 3. Similarity Detector (`intelligence/similarity_detector.py`)

Detects similar and duplicate content.

**Techniques:**

**SimHash:**
- 64-bit locality-sensitive hash
- Hamming distance comparison
- Similarity score (0.0 to 1.0)

**Content Hash:**
- MD5 hash for exact duplicate detection
- Fast comparison

**URL Similarity:**
- Path-based similarity scoring
- Same-domain comparison

**Methods:**
```python
# Compute fingerprints
fingerprint = detector.fingerprint(text, url)

# Compare two fingerprints
result = detector.compare(fp1, fp2)
# Returns: {
#     "is_duplicate": bool,
#     "is_exact_match": bool,
#     "content_similarity": float,
#     "url_similarity": float
# }
```

### 4. Content Classifier (`extraction/content_extractor.py`)

Already covered in Extraction System section.

---

## Rendering Engines

### 1. Static Fetcher (`rendering/static_fetcher.py`)

Fast HTTP client for static content.

**Features:**
- HTTP/2 support via httpx
- Automatic retry logic (tenacity)
- User-agent rotation
- Cookie support
- Proxy support
- Redirect following
- Timeout handling
- Blocking detection

**Blocking Detection:**
Detects anti-bot measures:
- 403 Forbidden
- 429 Rate Limited
- 503 with Cloudflare
- CAPTCHA indicators in HTML
- "Access denied", "Bot detected" phrases

**Configuration:**
```python
fetcher = StaticFetcher(
    timeout=30,
    max_retries=3,
    follow_redirects=True,
    proxy_url="http://proxy:8080"
)
result = await fetcher.fetch(url)
```

### 2. Playwright Renderer (`rendering/renderer.py`)

Full JavaScript rendering engine.

**Features:**
- Chromium-based rendering
- Full JavaScript execution
- Lazy loading support
- Infinite scroll handling
- "Load More" button clicking
- Screenshot capture
- Console log capture
- Network request monitoring
- Resource blocking for performance

**Rendering Process:**
1. Launch headless Chrome
2. Navigate to URL
3. Wait for network idle
4. Execute scroll handlers
5. Click "Load More" buttons
6. Wait for additional content
7. Extract final HTML

**Configuration:**
```python
renderer = PlaywrightRenderer(
    headless=True,
    timeout=30000,
    viewport_width=1920,
    viewport_height=1080,
    take_screenshots=False
)

result = await renderer.render(
    url,
    scroll_to_bottom=True,
    click_load_more=True
)
```

**Auto-Detection Mode:**
The crawler automatically switches to JavaScript rendering when:
- HTML content is < 1000 bytes
- No `<a>` links found in static HTML
- render_mode is set to "auto"

### 3. Scroll Handler (`rendering/scroll_handler.py`)

Handles infinite scroll and lazy loading.

**Techniques:**
- Progressive scrolling to bottom
- Wait for new content after each scroll
- Configurable scroll steps and delays
- Maximum scroll limit

---

## Storage Backends

### 1. JSON Output (`storage/json_output.py`)

File-based JSON storage (always enabled).

**Features:**
- Batch writing for efficiency
- Pretty-printed JSON
- Individual file support
- Summary generation
- Automatic directory creation

**Output Structure:**
```
output/
├── batch_0001.json
├── batch_0002.json
├── ...
└── summary.json
```

**Batch File Format:**
```json
{
    "batch": 1,
    "count": 100,
    "timestamp": "2026-02-14T12:00:00",
    "pages": [
        { "url": "...", "title": "...", ... }
    ]
}
```

### 2. MongoDB Storage (`storage/mongo_storage.py`)

NoSQL document storage for crawled data.

**Features:**
- Async operations (motor)
- Automatic indexing
- Full-text search
- Bulk operations
- Duplicate prevention

**Indexes Created:**
- URL (unique)
- Crawl timestamp
- Domain
- Text index on title and content

**Schema:**
```python
{
    "_id": ObjectId,
    "url": str,
    "domain": str,
    "title": str,
    "text_content": str,
    "html": str,
    "metadata": {},
    "links": {},
    "entities": {},
    "crawled_at": datetime,
    "updated_at": datetime
}
```

**Usage:**
```python
storage = MongoStorage(
    uri="mongodb://localhost:27017",
    database="iawic"
)
await storage.connect()
await storage.save_page(page_data)
```

### 3. Elasticsearch Storage (`storage/elastic_storage.py`)

Full-text search and analytics storage.

**Features:**
- Advanced full-text search
- Aggregations and analytics
- Real-time indexing
- Scalable storage

**Index Mapping:**
- Text fields with analyzers
- Keyword fields for exact matching
- Date fields for time-based queries
- Nested objects for structured data

### 4. Redis Queue (`storage/redis_queue.py`)

Distributed queue for URL frontier.

**Features:**
- Distributed crawling support
- Priority queues
- Pub/sub for coordination
- Atomic operations

---

## Utilities

### 1. Logger (`utils/logger.py`)

Structured logging system.

**Features:**
- Rich console output with colors
- File logging support
- Structured logs (JSON or console)
- Context variables
- Stack traces with locals

**Configuration:**
```python
setup_logging(
    log_level="INFO",
    log_file="crawler.log",
    enable_json=False
)

logger = get_logger("component_name")
logger.info("message", key=value)
```

### 2. User Agent Rotator (`utils/user_agents.py`)

Rotates user agents to mimic real browsers.

**Profiles Include:**
- Chrome (Windows, macOS, Linux)
- Firefox (Windows)
- Safari (macOS)
- Edge (Windows)

**Headers Generated:**
- User-Agent
- Accept
- Accept-Language
- Accept-Encoding
- DNT (Do Not Track)
- Sec-Fetch-* headers

### 3. Hash Utils (`utils/hash_utils.py`)

Hashing utilities for fingerprinting.

**Functions:**
- `md5_hash()`: MD5 hash
- `sha256_hash()`: SHA-256 hash
- `content_hash()`: Normalized content hash
- `url_hash()`: URL hash
- `SimHash`: SimHash implementation

### 4. File Utils (`utils/file_utils.py`)

File type detection and utilities.

**Functions:**
- `get_file_extension()`: Extract file extension
- `is_downloadable_file()`: Check if URL is downloadable
- `is_image_url()`: Check if URL is image
- `is_video_url()`: Check if URL is video
- `get_file_type()`: Get human-readable type
- `get_mime_type()`: Get MIME type

### 5. Proxy Manager (`utils/proxy_manager.py`)

Proxy pool management (for future implementation).

**Features:**
- Proxy rotation strategies
- Health checking
- Failure tracking

---

## Configuration

### Configuration System (`config.py`)

Hierarchical configuration using dataclasses.

**Configuration Levels:**
1. **Default values** in dataclasses
2. **Environment variables** (.env file)
3. **Configuration file** (JSON)
4. **CLI arguments** (highest priority)

### Main Configuration Classes

#### CrawlConfig
```python
url: str                          # Target URL
crawl_depth: int = 3              # Maximum depth
max_pages: int = 1000             # Page limit
follow_external_links: bool = False
include_subdomains: bool = True
strategy: CrawlStrategy = HYBRID  # BFS, DFS, HYBRID
render_mode: RenderMode = AUTO    # STATIC, JAVASCRIPT, AUTO
requests_per_second: float = 2.0
min_delay: float = 0.5
max_delay: float = 3.0
adaptive_delay: bool = True
page_timeout: int = 30
extract_images: bool = True
extract_videos: bool = True
extract_entities: bool = True
enable_dedup: bool = True
similarity_threshold: float = 0.85
rotate_user_agents: bool = True
respect_robots_txt: bool = True
output_dir: str = "./output"
```

#### StorageConfig
```python
mongo_enabled: bool = False
mongo_uri: str = "mongodb://localhost:27017"
mongo_db: str = "iawic"
elastic_enabled: bool = False
elastic_uri: str = "http://localhost:9200"
redis_enabled: bool = False
redis_uri: str = "redis://localhost:6379"
```

#### IAWICConfig
```python
crawl: CrawlConfig
storage: StorageConfig
proxy: ProxyConfig
log_level: str = "INFO"
workers: int = 4
```

### Configuration File Example

```json
{
    "crawl": {
        "crawl_depth": 5,
        "max_pages": 5000,
        "render_mode": "auto",
        "extract_entities": true,
        "similarity_threshold": 0.90
    },
    "storage": {
        "mongo_enabled": true,
        "elastic_enabled": true
    },
    "workers": 8,
    "log_level": "DEBUG"
}
```

---

## Data Flow

### Complete Crawl Cycle

```
1. INITIALIZATION
   ├─ Load configuration
   ├─ Initialize components
   ├─ Connect to storage backends
   └─ Add seed URL to frontier

2. WORKER LOOP (N concurrent workers)
   ├─ Get URL from frontier
   ├─ Check robots.txt
   ├─ Apply rate limiting
   ├─ Fetch/Render page
   │  ├─ Try static fetch first
   │  └─ Fall back to JS rendering if needed
   ├─ Extract page data
   │  ├─ Clean content
   │  ├─ Extract metadata
   │  ├─ Extract links
   │  ├─ Extract entities
   │  ├─ Extract media
   │  ├─ Detect language
   │  └─ Classify content
   ├─ Check for duplicates
   ├─ Save to storage backends
   ├─ Add discovered links to frontier
   └─ Mark URL as crawled

3. COMPLETION
   ├─ Flush remaining data
   ├─ Generate summary
   ├─ Close connections
   └─ Report statistics
```

### Data Transformations

```
Raw HTML
    ↓
[Content Cleaner]
    ↓
Cleaned HTML + Text
    ↓
[Extractors] → Metadata, Links, Entities, Media
    ↓
[Intelligence] → Language, Classification, Similarity
    ↓
Structured Page Data
    ↓
[Storage Backends] → JSON, MongoDB, Elasticsearch
```

### Page Data Structure

```python
{
    "url": "https://example.com/page",
    "domain": "example.com",
    "depth": 2,
    "title": "Page Title",
    "description": "Page description",
    "text_content": "Main text content...",
    "html": "<html>...</html>",  # Optional
    "metadata": {
        "canonical_url": "https://example.com/page",
        "language": "en",
        "author": "John Doe",
        "keywords": ["keyword1", "keyword2"],
        "og": {
            "type": "article",
            "image": "https://example.com/image.jpg"
        },
        "twitter": {
            "card": "summary",
            "site": "@example"
        }
    },
    "links": {
        "internal": ["https://example.com/page1", ...],
        "external": ["https://other.com/page", ...]
    },
    "entities": {
        "emails": ["contact@example.com"],
        "phones": ["+1-555-0123"],
        "social_links": [
            {"platform": "twitter", "url": "..."}
        ]
    },
    "language_detected": {
        "language": "en",
        "confidence": 0.99
    },
    "classification": {
        "type": "article",
        "confidence": 0.85
    }
}
```

---

## Usage Guide

### Basic Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Basic crawl
python main.py https://example.com

# With options
python main.py https://example.com \
    --depth 5 \
    --max-pages 5000 \
    --workers 8 \
    --output-dir ./data \
    --log-level DEBUG
```

### Configuration File Usage

```bash
# Create config.json
cat > config.json << EOF
{
    "crawl": {
        "crawl_depth": 3,
        "max_pages": 1000,
        "render_mode": "auto"
    },
    "workers": 4
}
EOF

# Use config file
python main.py https://example.com --config config.json
```

### Programmatic Usage

```python
import asyncio
from config import IAWICConfig
from core.crawler_engine import CrawlerEngine

async def main():
    # Configure
    config = IAWICConfig()
    config.crawl.crawl_depth = 3
    config.crawl.max_pages = 1000
    config.workers = 4
    
    # Create and start crawler
    crawler = CrawlerEngine(config)
    await crawler.start("https://example.com")
    
    # Get statistics
    stats = crawler.get_stats()
    print(f"Crawled {stats['pages_crawled']} pages")

if __name__ == "__main__":
    asyncio.run(main())
```

### Storage Backend Usage

```bash
# With MongoDB
python main.py https://example.com --mongo

# With Elasticsearch
python main.py https://example.com --elastic

# With both
python main.py https://example.com --mongo --elastic
```

### Environment Variables

```bash
# Create .env file
MONGO_URI=mongodb://localhost:27017
MONGO_DB=my_crawler_db
ELASTIC_URI=http://localhost:9200
ELASTIC_INDEX=web_pages
REDIS_URI=redis://localhost:6379
LOG_LEVEL=INFO
WORKERS=8

# Run
python main.py https://example.com --mongo --elastic
```

---

## Advanced Features

### 1. Authenticated Crawling

```python
from core.session_manager import SessionManager

session_manager = SessionManager()

# From cookies file
session_manager.load_cookies_from_file("cookies.json")

# Or set directly
session_manager.load_cookies_from_dict({
    "session_id": "abc123",
    "auth_token": "xyz789"
})

# Bearer token
session_manager.set_bearer_token("your_api_token")

# Apply to crawler
crawler = CrawlerEngine(config)
crawler.session_manager = session_manager
```

### 2. Custom Rate Limiting

```python
# Set custom crawl delay for specific domain
crawler.rate_limiter.set_crawl_delay("example.com", 2.0)

# Configure adaptive rate limiting
config.crawl.adaptive_delay = True
config.crawl.min_delay = 1.0
config.crawl.max_delay = 10.0
```

### 3. Priority URL Crawling

```python
from core.url_frontier import URLPriority

# Add high-priority URLs
await crawler.frontier.add(
    "https://example.com/important",
    depth=0,
    priority=URLPriority.CRITICAL
)

# Add deferred URLs
await crawler.frontier.add(
    "https://example.com/optional",
    depth=0,
    priority=URLPriority.DEFERRED
)
```

### 4. Custom Content Processing

```python
# Hook into extraction
original_extract = crawler._extract_page_data

async def custom_extract(url, html, depth):
    data = await original_extract(url, html, depth)
    
    # Custom processing
    data['custom_field'] = extract_custom_data(html)
    
    return data

crawler._extract_page_data = custom_extract
```

### 5. Distributed Crawling

Using Redis for distributed URL frontier:

```python
from storage.redis_queue import RedisQueue

# On each worker node
redis_queue = RedisQueue(redis_uri="redis://master:6379")
crawler.frontier = redis_queue  # Replace local frontier
```

### 6. Screenshot Capture

```python
renderer = PlaywrightRenderer(take_screenshots=True)
result = await renderer.render(url)

# Save screenshot
with open("screenshot.png", "wb") as f:
    f.write(result.screenshot)
```

### 7. Network Request Monitoring

```python
renderer = PlaywrightRenderer(capture_network=True)
result = await renderer.render(url)

# Analyze requests
for req in result.network_requests:
    print(f"{req['method']} {req['url']} ({req['resource_type']})")
```

---

## Performance Optimization

### Recommended Settings

**Small Site (<1000 pages):**
```python
workers = 2
requests_per_second = 1.0
crawl_depth = 3
```

**Medium Site (1000-10000 pages):**
```python
workers = 4
requests_per_second = 2.0
crawl_depth = 4
```

**Large Site (>10000 pages):**
```python
workers = 8-16
requests_per_second = 3.0
crawl_depth = 5
enable_dedup = True
store_html = False  # Save space
```

### Resource Management

**Memory:**
- Deduplication stores SimHash values in memory
- Consider disk-based storage for very large crawls
- Flush JSON batches frequently

**Network:**
- Use HTTP/2 for connection reuse
- Enable adaptive rate limiting
- Respect server capacity

**CPU:**
- Parsing and extraction are CPU-intensive
- Balance workers with CPU cores
- Use PyPy for better performance

---

## Error Handling

### Retry Logic

The crawler automatically retries failed requests with exponential backoff:
- Max retries: 3 (configurable)
- Failed URLs marked in frontier
- Re-added with lower priority

### Common Issues

**Anti-Bot Detection:**
- Switch to JavaScript rendering
- Enable proxy rotation
- Increase delays

**429 Rate Limiting:**
- Crawler automatically backs off
- Increases delay 3x
- Respects Retry-After header

**Timeouts:**
- Increase page_timeout
- Use static fetcher instead of renderer
- Check network connectivity

**Memory Issues:**
- Reduce workers
- Enable store_html = False
- Flush data more frequently

---

## Testing

Run unit tests:
```bash
pytest tests/ -v
```

Test components:
```bash
pytest tests/test_crawler.py
pytest tests/test_deduplication.py
pytest tests/test_extraction.py
pytest tests/test_normalization.py
```

---

## Best Practices

### 1. Respect Website Resources
- Set appropriate rate limits
- Respect robots.txt
- Honor crawl-delay directives
- Crawl during off-peak hours

### 2. Data Quality
- Enable content cleaning
- Use deduplication
- Validate extracted data
- Check for blocking

### 3. Monitoring
- Track crawl statistics
- Monitor error rates
- Log important events
- Set up alerts for failures

### 4. Storage
- Choose appropriate backends
- Index properly for queries
- Implement data retention policies
- Regular backups

### 5. Ethical Considerations
- Identify your crawler (User-Agent)
- Don't overwhelm servers
- Respect privacy and terms of service
- Handle personal data appropriately

---

## Architecture Decisions

### Why Async?
- Non-blocking I/O for better concurrency
- Efficient resource utilization
- Handles many concurrent requests
- Better than threading for I/O-bound tasks

### Why Priority Queue?
- Crawl important pages first
- Better depth-first search control
- Resource allocation optimization
- Flexible prioritization strategies

### Why SimHash?
- Fast near-duplicate detection
- Locality-sensitive hashing
- Low memory footprint
- Scalable to millions of documents

### Why Multiple Storage Backends?
- Different use cases
- Flexibility in deployment
- Testing and development
- Migration and backup options

---

## Future Enhancements

Potential improvements:
1. **Machine Learning**: Content quality scoring, automatic categorization
2. **Distributed Crawling**: Full Redis-based distributed system
3. **Advanced Scheduling**: Priority based on page importance, update frequency
4. **Content Analysis**: Sentiment analysis, topic modeling, summarization
5. **Visual Analysis**: Image recognition, layout analysis
6. **API Support**: RESTful API for crawler control
7. **Web UI**: Dashboard for monitoring and configuration
8. **Cloud Integration**: S3 storage, Cloud databases
9. **Advanced Anti-Blocking**: CAPTCHA solving, browser fingerprinting

---

## Conclusion

IAWIC is a comprehensive, production-ready web crawler that combines performance, intelligence, and flexibility. It's suitable for:
- **Research**: Academic web analysis, corpus building
- **Business**: Competitive intelligence, market research
- **SEO**: Site auditing, backlink analysis
- **Archival**: Website preservation, historical snapshots
- **Data Mining**: Large-scale web data extraction

The modular architecture allows easy customization and extension for specific use cases while maintaining robust core functionality.

---

## Support and Contribution

For questions, issues, or contributions, please refer to the project repository.

**License**: See LICENSE file in the repository.

**Version**: 0.1.0

**Last Updated**: February 2026
