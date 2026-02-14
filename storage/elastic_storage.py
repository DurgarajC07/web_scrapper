"""
Elasticsearch storage backend for crawled pages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

from utils.logger import get_logger

logger = get_logger("elastic_storage")


class ElasticStorage:
    """Async Elasticsearch storage for crawled data."""

    def __init__(self, uri: str, index: str = "iawic_pages"):
        """
        Initialize Elasticsearch storage.
        
        Args:
            uri: Elasticsearch connection URI
            index: Index name
        """
        self.uri = uri
        self.index = index
        self.client: AsyncElasticsearch | None = None

    async def connect(self) -> None:
        """Establish connection to Elasticsearch."""
        try:
            self.client = AsyncElasticsearch([self.uri])
            
            # Check connection
            await self.client.info()
            
            # Create index if it doesn't exist
            await self._create_index()
            
            logger.info("elasticsearch_connected", index=self.index)
        except Exception as e:
            logger.error("elasticsearch_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close Elasticsearch connection."""
        if self.client:
            await self.client.close()
            logger.info("elasticsearch_disconnected")

    async def _create_index(self) -> None:
        """Create index with mappings if it doesn't exist."""
        if not self.client:
            return

        # Check if index exists
        exists = await self.client.indices.exists(index=self.index)
        if exists:
            return

        # Define mappings
        mappings = {
            "properties": {
                "url": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "standard"},
                "description": {"type": "text"},
                "text_content": {"type": "text", "analyzer": "standard"},
                "language": {"type": "keyword"},
                "content_type": {"type": "keyword"},
                "crawled_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "metadata": {"type": "object", "enabled": False},
                "links": {"type": "keyword"},
                "emails": {"type": "keyword"},
                "phones": {"type": "keyword"},
            }
        }

        # Create index
        await self.client.indices.create(
            index=self.index,
            body={"mappings": mappings}
        )
        
        logger.info("index_created", index=self.index)

    async def save_page(self, page_data: dict) -> bool:
        """
        Index a crawled page.
        
        Args:
            page_data: Page data dictionary
            
        Returns:
            True if indexed successfully
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        # Add timestamps
        page_data["crawled_at"] = datetime.utcnow()
        page_data["updated_at"] = datetime.utcnow()

        # Use URL as document ID for deduplication
        doc_id = page_data.get("url", "")
        if not doc_id:
            logger.warning("no_url_in_page_data")
            return False

        try:
            await self.client.index(
                index=self.index,
                id=doc_id,
                document=page_data
            )
            logger.debug("page_indexed", url=doc_id)
            return True
        except Exception as e:
            logger.error("indexing_failed", url=doc_id, error=str(e))
            return False

    async def update_page(self, url: str, updates: dict) -> bool:
        """
        Update existing page document.
        
        Args:
            url: Page URL (document ID)
            updates: Fields to update
            
        Returns:
            True if updated successfully
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        updates["updated_at"] = datetime.utcnow()

        try:
            await self.client.update(
                index=self.index,
                id=url,
                doc=updates
            )
            return True
        except NotFoundError:
            return False
        except Exception as e:
            logger.error("update_failed", url=url, error=str(e))
            return False

    async def page_exists(self, url: str) -> bool:
        """Check if page exists in index."""
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        try:
            return await self.client.exists(index=self.index, id=url)
        except Exception:
            return False

    async def get_page(self, url: str) -> dict | None:
        """Retrieve page by URL."""
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        try:
            result = await self.client.get(index=self.index, id=url)
            return result["_source"]
        except NotFoundError:
            return None
        except Exception as e:
            logger.error("get_failed", url=url, error=str(e))
            return None

    async def search(self, query: str, size: int = 20) -> list[dict]:
        """
        Full-text search across pages.
        
        Args:
            query: Search query
            size: Maximum results
            
        Returns:
            List of matching pages
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        try:
            result = await self.client.search(
                index=self.index,
                body={
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "text_content", "description^2"]
                        }
                    },
                    "size": size
                }
            )
            
            return [hit["_source"] for hit in result["hits"]["hits"]]
        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            return []

    async def count_pages(self) -> int:
        """Get total page count."""
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        try:
            result = await self.client.count(index=self.index)
            return result["count"]
        except Exception:
            return 0

    async def bulk_save_pages(self, pages: list[dict]) -> int:
        """
        Bulk index pages.
        
        Args:
            pages: List of page data dictionaries
            
        Returns:
            Number of pages successfully indexed
        """
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        if not pages:
            return 0

        # Prepare bulk actions
        now = datetime.utcnow()
        actions = []
        for page in pages:
            page["crawled_at"] = now
            page["updated_at"] = now
            
            actions.append({
                "_index": self.index,
                "_id": page.get("url", ""),
                "_source": page
            })

        try:
            success, failed = await async_bulk(self.client, actions)
            logger.info("bulk_indexed", success=success, failed=len(failed))
            return success
        except Exception as e:
            logger.error("bulk_index_failed", error=str(e))
            return 0

    async def delete_index(self) -> None:
        """Delete the entire index."""
        if not self.client:
            raise RuntimeError("Not connected to Elasticsearch")

        try:
            await self.client.indices.delete(index=self.index)
            logger.info("index_deleted", index=self.index)
        except NotFoundError:
            logger.warning("index_not_found", index=self.index)
