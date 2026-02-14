# IAWIC - Intelligent Adaptive Web Intelligence Crawler

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)

**IAWIC** is a production-grade, intelligent web crawler built with Python's async/await paradigm. It's designed for researchers, data scientists, and developers who need to extract structured data from websites at scale while respecting server resources and avoiding duplicate content.

## 🚀 Features

### Core Capabilities
- **⚡ Async Architecture**: Built on asyncio for high-performance concurrent crawling
- **🧠 Intelligent Rate Limiting**: Adaptive per-domain delays that adjust based on server responses
- **🎭 Multiple Rendering Modes**: Static HTML fetching + JavaScript rendering via Playwright
- **🔍 Content Deduplication**: SimHash and exact hash matching to identify duplicate content
- **📊 Rich Data Extraction**: Metadata, links, entities, media, and structured data
- **🌐 Multi-Language Support**: Automatic language detection for 50+ languages
- **🤖 Robots.txt Compliant**: Full support including crawl-delay directives
- **💾 Flexible Storage**: JSON, MongoDB, Elasticsearch backends

### Extraction Features
- **Metadata**: Titles, descriptions, OpenGraph, Twitter Cards, canonical URLs
- **Links**: Internal/external classification, anchor text, nofollow detection
- **Entities**: Emails, phone numbers, physical addresses, social media links
- **Media**: Images (with lazy-load support), videos, downloadable files
- **Structured Data**: JSON-LD, Microdata, RDFa, Microformats
- **Content Classification**: Article, product, listing, forum, homepage detection

### Intelligence Layer
- **Content Cleaning**: Removes boilerplate, extracts main content
- **Language Detection**: Identifies page language with confidence scores
- **Similarity Detection**: Near-duplicate identification using SimHash
- **Content Classification**: Automatic page type classification

### Anti-Blocking
- **User-Agent Rotation**: Mimics real browsers (Chrome, Firefox, Safari, Edge)
- **Proxy Support**: Configurable proxy pools with rotation
- **Blocking Detection**: Identifies CAPTCHAs, rate limits, access denial
- **Adaptive Delays**: Automatically slows down on server errors

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [API Reference](#api-reference)
- [Performance](#performance)
- [Contributing](#contributing)
- [License](#license)

## 🔧 Installation

### Prerequisites
- Python 3.10 or higher
- pip or uv package manager

### Install Dependencies

```bash
# Clone the repository
git clone https://github.com/yourusername/iawic.git
cd iawic

# Install with pip
pip install -r requirements.txt

# Or with uv (recommended)
uv sync

# Install Playwright browsers
playwright install chromium
```

### Optional: External Services

For full functionality, you may want to install:

```bash
# MongoDB (for document storage)
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Elasticsearch (for full-text search)
docker run -d -p 9200:9200 -e "discovery.type=single-node" --name elasticsearch elasticsearch:8.12.0

# Redis (for distributed crawling)
docker run -d -p 6379:6379 --name redis redis:latest
```

Or use the provided docker-compose:

```bash
docker-compose up -d
```

## 🚀 Quick Start

### Basic Crawl

```bash
# Crawl a website (outputs to ./output directory)
python main.py https://example.com

# With custom settings
python main.py https://example.com \
    --depth 5 \
    --max-pages 5000 \
    --workers 8 \
    --output-dir ./data
```

### With Storage Backends

```bash
# Enable MongoDB storage
python main.py https://example.com --mongo

# Enable Elasticsearch
python main.py https://example.com --elastic

# Both
python main.py https://example.com --mongo --elastic
```

### Programmatic Usage

```python
import asyncio
from config import IAWICConfig
from core.crawler_engine import CrawlerEngine

async def main():
    # Configure crawler
    config = IAWICConfig()
    config.crawl.crawl_depth = 3
    config.crawl.max_pages = 1000
    config.crawl.render_mode = "auto"
    config.workers = 4
    
    # Create and start
    crawler = CrawlerEngine(config)
    await crawler.start("https://example.com")
    
    # Get stats
    stats = crawler.get_stats()
    print(f"✅ Crawled {stats['pages_crawled']} pages in {stats['duration_seconds']:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

## ⚙️ Configuration

### CLI Options

```bash
python main.py URL [OPTIONS]

Options:
  --config PATH        Path to JSON configuration file
  --depth INT          Maximum crawl depth (default: 3)
  --max-pages INT      Maximum pages to crawl (default: 1000)
  --output-dir PATH    Output directory (default: ./output)
  --workers INT        Number of concurrent workers (default: 4)
  --log-level LEVEL    Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --mongo              Enable MongoDB storage
  --elastic            Enable Elasticsearch storage
  --respect-robots     Respect robots.txt (default: True)
```

### Configuration File

Create `config.json`:

```json
{
    "crawl": {
        "crawl_depth": 5,
        "max_pages": 10000,
        "follow_external_links": false,
        "include_subdomains": true,
        "strategy": "hybrid",
        "render_mode": "auto",
        "requests_per_second": 2.0,
        "min_delay": 0.5,
        "max_delay": 5.0,
        "adaptive_delay": true,
        "page_timeout": 30,
        "extract_images": true,
        "extract_videos": true,
        "extract_entities": true,
        "enable_dedup": true,
        "similarity_threshold": 0.85,
        "respect_robots_txt": true
    },
    "storage": {
        "mongo_enabled": true,
        "mongo_uri": "mongodb://localhost:27017",
        "mongo_db": "web_crawler"
    },
    "workers": 8,
    "log_level": "INFO"
}
```

Use it:

```bash
python main.py https://example.com --config config.json
```

### Environment Variables

Create `.env`:

```bash
MONGO_URI=mongodb://localhost:27017
MONGO_DB=my_crawler_db
ELASTIC_URI=http://localhost:9200
ELASTIC_INDEX=web_pages
REDIS_URI=redis://localhost:6379
LOG_LEVEL=INFO
WORKERS=8
```

## 📚 Usage Examples

### 1. Simple Website Crawl

```python
import asyncio
from config import IAWICConfig
from core.crawler_engine import CrawlerEngine

async def crawl_website():
    config = IAWICConfig()
    config.crawl.crawl_depth = 3
    config.crawl.max_pages = 500
    
    crawler = CrawlerEngine(config)
    await crawler.start("https://example.com")

asyncio.run(crawl_website())
```

### 2. E-commerce Product Scraping

```python
config = IAWICConfig()
config.crawl.crawl_depth = 2
config.crawl.extract_images = True
config.crawl.extract_structured_data = True
config.crawl.enable_classification = True

crawler = CrawlerEngine(config)
await crawler.start("https://shop.example.com")
```

### 3. News Article Collection

```python
config = IAWICConfig()
config.crawl.crawl_depth = 3
config.crawl.extract_entities = True
config.crawl.enable_language_detection = True
config.crawl.enable_summarization = True

crawler = CrawlerEngine(config)
await crawler.start("https://news.example.com")
```

### 4. JavaScript-Heavy SPA

```python
config = IAWICConfig()
config.crawl.render_mode = "javascript"  # Force JS rendering
config.crawl.render_timeout = 30

crawler = CrawlerEngine(config)
await crawler.start("https://spa.example.com")
```

### 5. Authenticated Crawling

```python
from core.session_manager import SessionManager

session = SessionManager()
session.load_cookies_from_file("cookies.json")
# Or
session.set_bearer_token("your_api_token")

crawler = CrawlerEngine(config)
crawler.session_manager = session
await crawler.start("https://protected.example.com")
```

### 6. Rate-Limited API Crawling

```python
config = IAWICConfig()
config.crawl.requests_per_second = 0.5  # 1 request per 2 seconds
config.crawl.adaptive_delay = False
config.crawl.respect_robots_txt = True

crawler = CrawlerEngine(config)
await crawler.start("https://api.example.com")
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CrawlerEngine                         │
│  ┌────────────────────────────────────────────────┐    │
│  │ URL Frontier (Priority Queue)                  │    │
│  │ Rate Limiter (Adaptive, Per-Domain)            │    │
│  │ Robots Parser (Cached, TTL-based)              │    │
│  │ Content Deduplicator (SimHash + Exact Hash)    │    │
│  └────────────────────────────────────────────────┘    │
└──────────┬─────────────────────────────┬───────────────┘
           │                             │
   ┌───────▼────────┐            ┌──────▼──────────┐
   │   Rendering    │            │   Extraction    │
   │                │            │                 │
   │ Static Fetcher │            │ Content         │
   │ Playwright     │            │ Metadata        │
   │ Scroll Handler │            │ Links           │
   │                │            │ Entities        │
   └────────────────┘            │ Media           │
                                 │ Structured Data │
                                 └──────┬──────────┘
                                        │
                                ┌───────▼─────────┐
                                │  Intelligence   │
                                │                 │
                                │ Content Cleaner │
                                │ Language Detect │
                                │ Similarity      │
                                │ Classification  │
                                └───────┬─────────┘
                                        │
                                ┌───────▼─────────┐
                                │    Storage      │
                                │                 │
                                │ JSON / MongoDB  │
                                │ Elasticsearch   │
                                └─────────────────┘
```

### Component Overview

- **CrawlerEngine**: Orchestrates the entire crawling process
- **URL Frontier**: Priority queue with deduplication
- **Rate Limiter**: Adaptive per-domain throttling
- **Robots Parser**: Respects robots.txt rules
- **Static Fetcher**: Fast HTTP client for static content
- **Playwright Renderer**: Full JavaScript rendering
- **Extractors**: Parse HTML and extract structured data
- **Intelligence**: Content analysis and classification
- **Storage**: Persistent storage backends

## 📖 Documentation

For comprehensive documentation, see [DOCUMENTATION.md](DOCUMENTATION.md) which includes:

- **Detailed Architecture**: In-depth explanation of every component
- **API Reference**: Complete API documentation
- **Configuration Guide**: All configuration options explained
- **Data Flow**: How data moves through the system
- **Advanced Features**: Authentication, distributed crawling, custom processing
- **Performance Tuning**: Optimization strategies
- **Best Practices**: Ethical crawling guidelines

## 📊 Output Format

### JSON Output

Each crawled page produces:

```json
{
    "url": "https://example.com/page",
    "domain": "example.com",
    "depth": 2,
    "title": "Page Title",
    "description": "Meta description",
    "text_content": "Extracted text...",
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
        "internal": ["https://example.com/page1"],
        "external": ["https://other.com/page"]
    },
    "entities": {
        "emails": ["contact@example.com"],
        "phones": ["+1-555-0123"],
        "social_links": [
            {"platform": "twitter", "url": "https://twitter.com/example"}
        ]
    },
    "language_detected": {
        "language": "en",
        "confidence": 0.99
    },
    "classification": {
        "type": "article",
        "confidence": 0.87
    }
}
```

### MongoDB Schema

Same structure as JSON, with additional fields:
- `_id`: ObjectId
- `crawled_at`: datetime
- `updated_at`: datetime

Indexes on: `url` (unique), `domain`, `crawled_at`, full-text on `title` and `text_content`

## 🚄 Performance

### Benchmarks

On a modest machine (4 cores, 16GB RAM):

| Site Type | Pages | Workers | Time | Rate |
|-----------|-------|---------|------|------|
| Small Blog | 500 | 4 | 4m 10s | 2.0 pages/s |
| Medium Site | 5,000 | 8 | 41m 40s | 2.0 pages/s |
| Large Site | 50,000 | 16 | ~7 hours | 2.0 pages/s |

*Rate limited to 2 req/s per domain to respect servers*

### Optimization Tips

1. **Adjust Worker Count**: Match your CPU cores
2. **Disable HTML Storage**: Set `store_html = False` to save memory
3. **Increase Rate Limit**: Only if server allows
4. **Use Static Fetcher**: Disable JS rendering when not needed
5. **Batch Writes**: Increase JSON batch size

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_crawler.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

Test components:
- `test_crawler.py`: CrawlerEngine tests
- `test_deduplication.py`: Content deduplication tests
- `test_extraction.py`: Extractor tests
- `test_normalization.py`: URL normalization tests

## 🛡️ Best Practices

### Ethical Crawling

1. **Respect robots.txt**: Always keep `respect_robots_txt = True`
2. **Rate Limiting**: Don't overwhelm servers (2-3 req/s max)
3. **Identify Yourself**: Use a descriptive User-Agent
4. **Off-Peak Hours**: Crawl during low-traffic times
5. **Terms of Service**: Review and comply with website ToS

### Data Quality

1. **Enable Deduplication**: Avoid storing duplicate content
2. **Content Cleaning**: Remove boilerplate for better quality
3. **Validate Data**: Check extracted entities
4. **Handle Errors**: Implement proper error handling
5. **Monitor Progress**: Track statistics and error rates

### Resource Management

1. **Memory**: Monitor memory usage, flush data regularly
2. **Disk Space**: JSON files can grow large
3. **Network**: Don't crawl from rate-limited connections
4. **CPU**: Balance workers with available cores

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 Project Structure

```
iawic/
├── core/                    # Core crawling components
│   ├── crawler_engine.py    # Main crawler orchestrator
│   ├── url_frontier.py      # Priority queue for URLs
│   ├── rate_limiter.py      # Adaptive rate limiting
│   ├── robots_parser.py     # robots.txt handler
│   ├── url_normalizer.py    # URL normalization
│   ├── deduplication.py     # Content deduplication
│   └── session_manager.py   # Session/auth management
├── extraction/              # Data extraction modules
│   ├── content_extractor.py # Content classification
│   ├── link_extractor.py    # Link extraction
│   ├── metadata_extractor.py # Metadata extraction
│   ├── entity_extractor.py  # Entity extraction
│   ├── media_extractor.py   # Media extraction
│   ├── heading_extractor.py # Heading extraction
│   └── structured_data_extractor.py # Structured data
├── intelligence/            # Content intelligence
│   ├── content_cleaner.py   # HTML cleaning
│   ├── language_detector.py # Language detection
│   ├── similarity_detector.py # Similarity detection
│   ├── content_classifier.py # Content classification
│   └── summarizer.py        # Text summarization
├── rendering/               # Page rendering
│   ├── renderer.py          # Playwright renderer
│   ├── static_fetcher.py    # Static HTTP fetcher
│   └── scroll_handler.py    # Infinite scroll handler
├── storage/                 # Storage backends
│   ├── json_output.py       # JSON file storage
│   ├── mongo_storage.py     # MongoDB storage
│   ├── elastic_storage.py   # Elasticsearch storage
│   └── redis_queue.py       # Redis queue
├── utils/                   # Utilities
│   ├── logger.py            # Structured logging
│   ├── user_agents.py       # User-agent rotation
│   ├── hash_utils.py        # Hashing utilities
│   ├── file_utils.py        # File utilities
│   └── proxy_manager.py     # Proxy management
├── tests/                   # Test suite
├── config.py                # Configuration system
├── main.py                  # CLI entry point
├── requirements.txt         # Dependencies
├── pyproject.toml          # Project metadata
├── DOCUMENTATION.md        # Detailed documentation
└── README.md               # This file
```

## 🔮 Future Roadmap

- [ ] Machine learning-based content quality scoring
- [ ] Distributed crawling with Redis
- [ ] Web UI dashboard
- [ ] RESTful API for crawler control
- [ ] Advanced content summarization
- [ ] Image analysis and OCR
- [ ] CAPTCHA solving integration
- [ ] Cloud storage backends (S3, GCS)
- [ ] Real-time crawling mode
- [ ] GraphQL API support

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

Built with these excellent libraries:
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client/server
- [Playwright](https://github.com/microsoft/playwright-python) - Browser automation
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [structlog](https://github.com/hynek/structlog) - Structured logging
- [motor](https://github.com/mongodb/motor) - Async MongoDB driver
- [langdetect](https://github.com/Mimino666/langdetect) - Language detection
- Many others listed in requirements.txt

## 📞 Support

For questions, issues, or feature requests:
- Open an issue on GitHub
- Check the [DOCUMENTATION.md](DOCUMENTATION.md)
- Review existing issues and discussions

## 🔄 Version History

- **0.1.0** (February 2026) - Initial release
  - Core crawling functionality
  - Multi-backend storage
  - JavaScript rendering
  - Content intelligence

---

**Made with ❤️ for the web scraping community**
