"""
MongoDB storage backend for crawled pages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from utils.logger import get_logger

logger = get_logger("mongo_storage")


class MongoStorage:
    """Async MongoDB storage for crawled data."""

    def __init__(self, uri: str, database: str = "iawic"):
        """
        Initialize MongoDB storage.
        
        Args:
            uri: MongoDB connection URI
            database: Database name
        """
        self.uri = uri
        self.database_name = database
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.database_name]
            
            # Create indexes
            await self._create_indexes()
            
            logger.info("mongodb_connected", database=self.database_name)
        except PyMongoError as e:
            logger.error("mongodb_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("mongodb_disconnected")

    async def _create_indexes(self) -> None:
        """Create necessary indexes."""
        if not self.db:
            return

        pages = self.db.pages
        
        # Unique index on URL
        await pages.create_index("url", unique=True)
        
        # Index on crawl timestamp
        await pages.create_index("crawled_at")
        
        # Index on domain
        await pages.create_index("domain")
        
        # Text index for full-text search
        await pages.create_index([("title", "text"), ("text_content", "text")])

    async def save_page(self, page_data: dict) -> bool:
        """
        Save crawled page data.
        
        Args:
            page_data: Dictionary containing page data
            
        Returns:
            True if saved, False if duplicate
        """
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        # Add timestamp
        page_data["crawled_at"] = datetime.utcnow()
        page_data["updated_at"] = datetime.utcnow()

        try:
            await self.db.pages.insert_one(page_data)
            logger.debug("page_saved", url=page_data.get("url"))
            return True
        except DuplicateKeyError:
            logger.debug("duplicate_page", url=page_data.get("url"))
            return False
        except PyMongoError as e:
            logger.error("save_failed", url=page_data.get("url"), error=str(e))
            raise

    async def update_page(self, url: str, updates: dict) -> bool:
        """
        Update existing page data.
        
        Args:
            url: Page URL
            updates: Fields to update
            
        Returns:
            True if updated, False if not found
        """
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        updates["updated_at"] = datetime.utcnow()

        result = await self.db.pages.update_one(
            {"url": url},
            {"$set": updates}
        )

        return result.modified_count > 0

    async def page_exists(self, url: str) -> bool:
        """Check if page URL exists in database."""
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        count = await self.db.pages.count_documents({"url": url}, limit=1)
        return count > 0

    async def get_page(self, url: str) -> dict | None:
        """Retrieve page data by URL."""
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        return await self.db.pages.find_one({"url": url})

    async def get_pages_by_domain(self, domain: str, limit: int = 100) -> list[dict]:
        """Get all pages from a domain."""
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        cursor = self.db.pages.find({"domain": domain}).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_pages(self) -> int:
        """Get total page count."""
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        return await self.db.pages.count_documents({})

    async def search_pages(self, query: str, limit: int = 20) -> list[dict]:
        """
        Full-text search across pages.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching pages
        """
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        cursor = self.db.pages.find(
            {"$text": {"$search": query}}
        ).limit(limit)
        
        return await cursor.to_list(length=limit)

    async def bulk_save_pages(self, pages: list[dict]) -> int:
        """
        Bulk insert pages.
        
        Args:
            pages: List of page data dictionaries
            
        Returns:
            Number of pages successfully inserted
        """
        if not self.db:
            raise RuntimeError("Not connected to MongoDB")

        if not pages:
            return 0

        # Add timestamps
        now = datetime.utcnow()
        for page in pages:
            page["crawled_at"] = now
            page["updated_at"] = now

        try:
            result = await self.db.pages.insert_many(pages, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            # Some may have been inserted before error
            logger.warning("bulk_insert_partial", error=str(e))
            return 0
