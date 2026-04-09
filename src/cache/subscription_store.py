"""MongoDB CRUD store for topic subscriptions."""

from datetime import datetime, timezone
from typing import Any, Literal
import asyncio

from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

from src.config.settings import settings
from src.models.subscription import Subscription
from src.utils.logger import logger


class SubscriptionStore:
    """Persistent store for user topic subscriptions."""

    def __init__(self):
        self.client: MongoClient | None = None
        self.database_name = settings.mongo_database
        self.collection_name = "subscriptions"

    def _get_collection_sync(self):
        if self.client is None:
            self.client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command("ping")

        client = self.client
        if client is None:
            raise RuntimeError("MongoDB client initialization failed")

        collection = client[self.database_name][self.collection_name]
        collection.create_index([("user_id", ASCENDING), ("topic", ASCENDING)], unique=True)
        collection.create_index([("status", ASCENDING), ("execution_day", ASCENDING)])
        collection.create_index([("expires_at", ASCENDING)])
        return collection

    async def _run(self, fn):
        return await asyncio.to_thread(fn)

    async def ping(self) -> tuple[bool, str]:
        """Check whether MongoDB subscription storage is reachable."""
        def _sync_ping() -> tuple[bool, str]:
            try:
                collection = self._get_collection_sync()
                # Force a lightweight call on the target collection namespace.
                collection.estimated_document_count()
                return True, "ok"
            except Exception as exc:
                return False, str(exc)

        return await self._run(_sync_ping)

    async def create(self, subscription: Subscription) -> Literal["created", "already_active", "reactivated", "failed"]:
        def _sync_create() -> Literal["created", "already_active", "reactivated", "failed"]:
            collection = self._get_collection_sync()
            existing = collection.find_one(
                {
                    "user_id": subscription.user_id,
                    "topic": subscription.topic,
                },
                {"_id": 1, "status": 1},
            )
            if existing:
                if existing.get("status") == "active":
                    return "already_active"

                # Allow explicit re-subscribe for previously expired/inactive records.
                result = collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": subscription.model_dump(mode="python")},
                )
                return "reactivated" if result.matched_count > 0 else "failed"

            collection.insert_one(subscription.model_dump(mode="python"))
            return "created"

        try:
            return await self._run(_sync_create)
        except DuplicateKeyError:
            # Race condition: another instance created the same user/topic just before this request.
            return "already_active"

        except Exception as exc:
            logger.error(f"Failed to create subscription: {exc}")
            return "failed"

    async def get_by_user(self, user_id: str) -> list[Subscription]:
        def _sync_get() -> list[Subscription]:
            collection = self._get_collection_sync()
            docs = list(collection.find({"user_id": user_id}, {"_id": 0}))
            return [Subscription.model_validate(doc) for doc in docs]

        try:
            return await self._run(_sync_get)
        except Exception as exc:
            logger.error(f"Failed to fetch subscriptions for user {user_id}: {exc}")
            return []

    async def get_active_by_day(self, execution_day: int) -> list[Subscription]:
        def _sync_get() -> list[Subscription]:
            collection = self._get_collection_sync()
            docs = list(
                collection.find(
                    {
                        "status": "active",
                        "execution_day": execution_day,
                        "expires_at": {"$gte": datetime.now(timezone.utc)},
                    },
                    {"_id": 0},
                )
            )
            return [Subscription.model_validate(doc) for doc in docs]

        try:
            return await self._run(_sync_get)
        except Exception as exc:
            logger.error(f"Failed to fetch active subscriptions for day {execution_day}: {exc}")
            return []

    async def update(self, user_id: str, topic: str, updates: dict[str, Any]) -> bool:
        def _sync_update() -> bool:
            collection = self._get_collection_sync()
            result = collection.update_one(
                {"user_id": user_id, "topic": topic, "status": "active"},
                {"$set": updates},
            )
            return result.modified_count > 0

        try:
            return await self._run(_sync_update)
        except Exception as exc:
            logger.error(f"Failed to update subscription for {user_id}/{topic}: {exc}")
            return False

    async def delete(self, user_id: str, topic: str) -> bool:
        def _sync_delete() -> bool:
            collection = self._get_collection_sync()
            result = collection.delete_one({"user_id": user_id, "topic": topic})
            return result.deleted_count > 0

        try:
            return await self._run(_sync_delete)
        except Exception as exc:
            logger.error(f"Failed to delete subscription for {user_id}/{topic}: {exc}")
            return False

    async def get_count_by_user(self, user_id: str) -> int:
        def _sync_count() -> int:
            collection = self._get_collection_sync()
            return int(collection.count_documents({"user_id": user_id, "status": "active"}))

        try:
            return await self._run(_sync_count)
        except Exception as exc:
            logger.error(f"Failed to count subscriptions for user {user_id}: {exc}")
            return 0

    async def get_subscription(self, user_id: str, topic: str) -> Subscription | None:
        def _sync_get_one() -> Subscription | None:
            collection = self._get_collection_sync()
            doc = collection.find_one(
                {"user_id": user_id, "topic": topic, "status": "active"},
                {"_id": 0},
            )
            return Subscription.model_validate(doc) if doc else None

        try:
            return await self._run(_sync_get_one)
        except Exception as exc:
            logger.error(f"Failed to fetch subscription for {user_id}/{topic}: {exc}")
            return None

    async def expire_old_subscriptions(self) -> int:
        now = datetime.now(timezone.utc)

        def _sync_expire() -> int:
            collection = self._get_collection_sync()
            result = collection.update_many(
                {
                    "status": "active",
                    "expires_at": {"$lt": now},
                },
                {
                    "$set": {
                        "status": "expired",
                        "last_checked": now,
                    }
                },
            )
            return int(result.modified_count)

        try:
            return await self._run(_sync_expire)
        except Exception as exc:
            logger.error(f"Failed to expire old subscriptions: {exc}")
            return 0

    async def close(self) -> None:
        if self.client is not None:
            await asyncio.to_thread(self.client.close)
            self.client = None
