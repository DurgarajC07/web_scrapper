"""
Media extraction: images, videos, and downloadable files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from utils.file_utils import (
    get_file_extension,
    get_file_type,
    is_downloadable_file,
    DOWNLOADABLE_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from utils.logger import get_logger

logger = get_logger("media_extractor")


@dataclass
class ImageInfo:
    url: str
    alt: str = ""
    title: str = ""
    width: int | None = None
    height: int | None = None
    format: str = ""


@dataclass
class VideoInfo:
    url: str
    type: str = ""  # html5, iframe, embed
    source: str = ""  # youtube, vimeo, self-hosted
    poster: str = ""
    title: str = ""


@dataclass
class FileInfo:
    url: str
    file_type: str = ""
    file_size: int | None = None
    filename: str = ""


@dataclass
class MediaData:
    images: list[dict] = field(default_factory=list)
    videos: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)


class MediaExtractor:
    """Extracts all media resources from HTML pages."""

    # Video platform patterns
    VIDEO_PLATFORMS = {
        "youtube": [
            r"youtube\.com/embed/",
            r"youtube\.com/watch",
            r"youtu\.be/",
            r"youtube-nocookie\.com/embed/",
        ],
        "vimeo": [
            r"vimeo\.com/",
            r"player\.vimeo\.com/",
        ],
        "dailymotion": [
            r"dailymotion\.com/",
        ],
        "wistia": [
            r"wistia\.com/",
            r"wistia\.net/",
        ],
    }

    def extract(self, html: str, base_url: str = "") -> MediaData:
        """Extract all media from HTML."""
        soup = BeautifulSoup(html, "lxml")
        media = MediaData()

        media.images = self._extract_images(soup, base_url)
        media.videos = self._extract_videos(soup, base_url)
        media.files = self._extract_files(soup, base_url)

        return media

    def _extract_images(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict]:
        """Extract all images from page."""
        images = []
        seen_urls = set()

        for img in soup.find_all("img"):
            # Get source URL (handle lazy loading)
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("data-srcset", "").split(",")[0].split()[0]
                if img.get("data-srcset")
                else ""
            )

            if not src or src.startswith("data:"):
                continue

            # Make absolute
            if base_url:
                src = urljoin(base_url, src)

            if src in seen_urls:
                continue
            seen_urls.add(src)

            # Get dimensions
            width = self._parse_dimension(img.get("width"))
            height = self._parse_dimension(img.get("height"))

            # Get format
            ext = get_file_extension(src)
            fmt = ext.lstrip(".").upper() if ext else ""

            images.append({
                "url": src,
                "alt": img.get("alt", "").strip(),
                "title": img.get("title", "").strip(),
                "width": width,
                "height": height,
                "format": fmt,
            })

        # Also check <picture> elements
        for picture in soup.find_all("picture"):
            for source in picture.find_all("source"):
                srcset = source.get("srcset", "")
                if srcset:
                    src = srcset.split(",")[0].split()[0]
                    if base_url:
                        src = urljoin(base_url, src)
                    if src not in seen_urls:
                        seen_urls.add(src)
                        ext = get_file_extension(src)
                        images.append({
                            "url": src,
                            "alt": "",
                            "title": "",
                            "width": None,
                            "height": None,
                            "format": ext.lstrip(".").upper() if ext else "",
                        })

        # Background images from inline styles
        for tag in soup.find_all(style=re.compile(r"background-image")):
            style = tag.get("style", "")
            urls = re.findall(r"url\(['\"]?(.*?)['\"]?\)", style)
            for url in urls:
                if url.startswith("data:"):
                    continue
                if base_url:
                    url = urljoin(base_url, url)
                if url not in seen_urls:
                    seen_urls.add(url)
                    ext = get_file_extension(url)
                    images.append({
                        "url": url,
                        "alt": "",
                        "title": "",
                        "width": None,
                        "height": None,
                        "format": ext.lstrip(".").upper() if ext else "",
                    })

        return images

    def _extract_videos(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict]:
        """Extract all videos from page."""
        videos = []
        seen_urls = set()

        # HTML5 <video> elements
        for video in soup.find_all("video"):
            sources = video.find_all("source")
            if sources:
                for source in sources:
                    src = source.get("src", "")
                    if src and src not in seen_urls:
                        if base_url:
                            src = urljoin(base_url, src)
                        seen_urls.add(src)
                        videos.append({
                            "url": src,
                            "type": "html5",
                            "source": "self-hosted",
                            "poster": video.get("poster", ""),
                            "title": "",
                        })
            else:
                src = video.get("src", "")
                if src and src not in seen_urls:
                    if base_url:
                        src = urljoin(base_url, src)
                    seen_urls.add(src)
                    videos.append({
                        "url": src,
                        "type": "html5",
                        "source": "self-hosted",
                        "poster": video.get("poster", ""),
                        "title": "",
                    })

        # Iframe embeds
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or ""
            if not src:
                continue

            if base_url:
                src = urljoin(base_url, src)

            # Check if it's a video platform
            platform = self._identify_video_platform(src)
            if platform and src not in seen_urls:
                seen_urls.add(src)
                videos.append({
                    "url": src,
                    "type": "iframe",
                    "source": platform,
                    "poster": "",
                    "title": iframe.get("title", ""),
                })

        # <embed> and <object> tags
        for embed in soup.find_all(["embed", "object"]):
            src = embed.get("src") or embed.get("data", "")
            if src and src not in seen_urls:
                if base_url:
                    src = urljoin(base_url, src)
                ext = get_file_extension(src)
                if ext in VIDEO_EXTENSIONS:
                    seen_urls.add(src)
                    videos.append({
                        "url": src,
                        "type": "embed",
                        "source": "self-hosted",
                        "poster": "",
                        "title": "",
                    })

        return videos

    def _extract_files(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict]:
        """Extract downloadable files."""
        files = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if base_url:
                href = urljoin(base_url, href)

            if is_downloadable_file(href) and href not in seen_urls:
                seen_urls.add(href)
                ext = get_file_extension(href)
                filename = urlparse(href).path.split("/")[-1]

                files.append({
                    "url": href,
                    "file_type": get_file_type(href),
                    "file_size": None,  # Would need HEAD request
                    "filename": filename,
                })

        return files

    def _identify_video_platform(self, url: str) -> str | None:
        """Identify video platform from URL."""
        for platform, patterns in self.VIDEO_PLATFORMS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.I):
                    return platform
        return None

    def _parse_dimension(self, value: str | None) -> int | None:
        """Parse width/height attribute to integer."""
        if not value:
            return None
        try:
            # Remove 'px' suffix if present
            clean = str(value).replace("px", "").strip()
            return int(float(clean))
        except (ValueError, TypeError):
            return None