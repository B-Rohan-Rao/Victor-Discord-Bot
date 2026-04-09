from datetime import datetime, timedelta, timezone

import pytest

from src.cache.subscription_store import SubscriptionStore
from src.models.subscription import Subscription


class _UpdateResult:
    def __init__(self, matched_count: int):
        self.matched_count = matched_count


class _CollectionStub:
    def __init__(self, existing=None, raise_duplicate: bool = False):
        self._existing = existing
        self.raise_duplicate = raise_duplicate
        self.insert_calls = 0
        self.update_calls = 0

    def find_one(self, *_args, **_kwargs):
        return self._existing

    def insert_one(self, _doc):
        self.insert_calls += 1
        if self.raise_duplicate:
            from pymongo.errors import DuplicateKeyError

            raise DuplicateKeyError("duplicate")

    def update_one(self, _query, _update):
        self.update_calls += 1
        return _UpdateResult(matched_count=1)


def _sub() -> Subscription:
    now = datetime.now(timezone.utc)
    return Subscription(
        user_id="u1",
        topic="topic-a",
        category="dynamic",
        execution_day=3,
        last_known_urls=[],
        created_at=now,
        expires_at=now + timedelta(days=60),
        status="active",
    )


@pytest.mark.asyncio
async def test_create_returns_created_for_new_record(monkeypatch: pytest.MonkeyPatch):
    store = SubscriptionStore()
    collection = _CollectionStub(existing=None)
    monkeypatch.setattr(store, "_get_collection_sync", lambda: collection)

    result = await store.create(_sub())

    assert result == "created"
    assert collection.insert_calls == 1


@pytest.mark.asyncio
async def test_create_returns_already_active_for_existing_active(monkeypatch: pytest.MonkeyPatch):
    store = SubscriptionStore()
    collection = _CollectionStub(existing={"_id": "1", "status": "active"})
    monkeypatch.setattr(store, "_get_collection_sync", lambda: collection)

    result = await store.create(_sub())

    assert result == "already_active"
    assert collection.insert_calls == 0


@pytest.mark.asyncio
async def test_create_returns_reactivated_for_existing_inactive(monkeypatch: pytest.MonkeyPatch):
    store = SubscriptionStore()
    collection = _CollectionStub(existing={"_id": "1", "status": "expired"})
    monkeypatch.setattr(store, "_get_collection_sync", lambda: collection)

    result = await store.create(_sub())

    assert result == "reactivated"
    assert collection.update_calls == 1


@pytest.mark.asyncio
async def test_create_returns_already_active_on_duplicate_key_race(monkeypatch: pytest.MonkeyPatch):
    store = SubscriptionStore()
    collection = _CollectionStub(existing=None, raise_duplicate=True)
    monkeypatch.setattr(store, "_get_collection_sync", lambda: collection)

    result = await store.create(_sub())

    assert result == "already_active"
