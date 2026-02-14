"""
File type detection and downloadable resource identification.
"""

import mimetypes
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath


# File extensions considered downloadable
DOWNLOADABLE_EXTENSIONS = {
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf", ".tex", ".txt", ".csv",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    # Media
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv",
    ".wav", ".flac", ".aac", ".ogg", ".webm",
    # Images (high-res / raw)
    ".svg", ".eps", ".tiff", ".raw", ".psd", ".ai",
    # Data
    ".json", ".xml", ".yaml", ".yml", ".sql", ".db",
    # Executables (for detection, not download)
    ".exe", ".msi", ".dmg", ".apk", ".deb", ".rpm",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".bmp", ".ico", ".tiff", ".avif",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".avi", ".mov", ".wmv",
    ".flv", ".mkv", ".m4v", ".ogv",
}


def get_file_extension(url: str) -> str:
    """Extract file extension from URL."""
    parsed = urlparse(unquote(url))
    path = PurePosixPath(parsed.path)
    return path.suffix.lower()


def is_downloadable_file(url: str) -> bool:
    """Check if URL points to a downloadable file."""
    ext = get_file_extension(url)
    return ext in DOWNLOADABLE_EXTENSIONS


def is_image_url(url: str) -> bool:
    ext = get_file_extension(url)
    return ext in IMAGE_EXTENSIONS


def is_video_url(url: str) -> bool:
    ext = get_file_extension(url)
    return ext in VIDEO_EXTENSIONS


def get_file_type(url: str) -> str:
    """Get human-readable file type from URL."""
    ext = get_file_extension(url)
    type_map = {
        ".pdf": "PDF Document",
        ".doc": "Word Document",
        ".docx": "Word Document",
        ".xls": "Excel Spreadsheet",
        ".xlsx": "Excel Spreadsheet",
        ".ppt": "PowerPoint Presentation",
        ".pptx": "PowerPoint Presentation",
        ".zip": "ZIP Archive",
        ".rar": "RAR Archive",
        ".csv": "CSV File",
        ".json": "JSON File",
        ".xml": "XML File",
    }
    return type_map.get(ext, ext.lstrip(".").upper() if ext else "Unknown")


def get_mime_type(url: str) -> str:
    """Get MIME type from URL."""
    mime, _ = mimetypes.guess_type(url)
    return mime or "application/octet-stream"


def is_webpage_url(url: str) -> bool:
    """Check if URL likely points to a webpage (not a file)."""
    ext = get_file_extension(url)
    if not ext:
        return True
    webpage_extensions = {".html", ".htm", ".php", ".asp", ".aspx", ".jsp", ""}
    return ext in webpage_extensions