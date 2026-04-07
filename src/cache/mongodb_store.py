"""
MongoDB persistence layer for research results.
Stores canonical records and supports retrieval by query hash.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import asyncio
import hashlib
from pymongo import MongoClient, DESCENDING
from src.config.settings import settings


class MongoStore:
    """MongoDB store for persistent research records."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.database_name = settings.mongo_database
        self.collection_name = settings.mongo_collection

    @staticmethod
    def _hash_query(query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()

    def _get_collection_sync(self):
        if self.client is None:
            self.client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
            # Trigger connection early so failures surface quickly.
            self.client.admin.command("ping")

        client = self.client
        if client is None:
            raise RuntimeError("MongoDB client initialization failed")

        db = client[self.database_name]
        collection = db[self.collection_name]
        collection.create_index("query_hash")
        collection.create_index([("created_at", DESCENDING)])
        return collection

    async def _get_collection(self):
        return await asyncio.to_thread(self._get_collection_sync)

    async def get_recent(self, query: str, ttl_seconds: int) -> Optional[Any]:
        """Return the latest non-expired result for a query."""
        query_hash = self._hash_query(query)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)

        def _sync_get():
            collection = self._get_collection_sync()
            doc = collection.find_one(
                {
                    "query_hash": query_hash,
                    "created_at": {"$gte": cutoff},
                },
                sort=[("created_at", DESCENDING)],
                projection={"_id": 0, "result": 1},
            )
            return doc.get("result") if doc else None

        try:
            return await asyncio.to_thread(_sync_get)
        except Exception:
            return None

    async def save(self, query: str, result: Any) -> bool:
        """Store a research result document."""
        query_hash = self._hash_query(query)

        def _sync_save():
            collection = self._get_collection_sync()
            collection.insert_one(
                {
                    "query": query,
                    "query_hash": query_hash,
                    "result": result,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            return True

        try:
            return await asyncio.to_thread(_sync_save)
        except Exception:
            return False

    async def close(self) -> None:
        if self.client is not None:
            await asyncio.to_thread(self.client.close)
            self.client = None
