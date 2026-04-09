from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.settings import settings
from src.models.research import Citation
from src.models.subscription import Subscription
from src.scheduler.subscription_worker import SubscriptionWorker


def _make_subscription(last_known_urls: list[str] | None = None) -> Subscription:
    return Subscription(
        user_id="1234567890",
        topic="Latest AI chip updates",
        category="dynamic",
        execution_day=datetime.now(timezone.utc).weekday(),
        last_known_urls=last_known_urls or [],
        status="active",
    )


@pytest.mark.asyncio
async def test_process_subscription_sends_dm_and_updates_when_new_urls_found() -> None:
    store = MagicMock()
    store.update = AsyncMock(return_value=True)

    web_search = MagicMock()
    web_search.search_incremental = AsyncMock(
        return_value=[
            Citation(title="Old", url="https://example.com/old", snippet=""),
            Citation(title="New", url="https://example.com/new", snippet=""),
        ]
    )

    notifier = MagicMock()
    notifier.create_update_embed = MagicMock(return_value=object())
    notifier.send_dm = AsyncMock(return_value=True)

    orchestrator = MagicMock()
    orchestrator.execute = AsyncMock(return_value=SimpleNamespace(summary="Weekly summary text"))

    worker = SubscriptionWorker(
        store=store,
        web_search=web_search,
        notifier=notifier,
        orchestrator=orchestrator,
        bot_client=object(),
    )

    subscription = _make_subscription(last_known_urls=["https://example.com/old"])

    await worker._process_subscription(subscription)

    web_search.search_incremental.assert_awaited_once_with(
        subscription.topic,
        max_results=10,
        days_back=settings.update_check_days,
    )
    orchestrator.execute.assert_awaited_once_with(subscription.topic, notify_discord=False)
    notifier.send_dm.assert_awaited_once()
    store.update.assert_awaited_once()

    update_args = store.update.await_args.args
    assert update_args[0] == subscription.user_id
    assert update_args[1] == subscription.topic
    payload = update_args[2]
    assert sorted(payload["last_known_urls"]) == sorted(
        ["https://example.com/old", "https://example.com/new"]
    )
    assert isinstance(payload["last_checked"], datetime)


@pytest.mark.asyncio
async def test_process_subscription_skips_when_no_new_urls() -> None:
    store = MagicMock()
    store.update = AsyncMock(return_value=True)

    web_search = MagicMock()
    web_search.search_incremental = AsyncMock(
        return_value=[
            Citation(title="Old", url="https://example.com/old", snippet=""),
        ]
    )

    notifier = MagicMock()
    notifier.create_update_embed = MagicMock(return_value=object())
    notifier.send_dm = AsyncMock(return_value=True)

    orchestrator = MagicMock()
    orchestrator.execute = AsyncMock(return_value=SimpleNamespace(summary="unused"))

    worker = SubscriptionWorker(
        store=store,
        web_search=web_search,
        notifier=notifier,
        orchestrator=orchestrator,
        bot_client=object(),
    )

    subscription = _make_subscription(last_known_urls=["https://example.com/old"])

    await worker._process_subscription(subscription)

    orchestrator.execute.assert_not_awaited()
    notifier.send_dm.assert_not_awaited()
    store.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_daily_checks_processes_today_subscriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    today = datetime.now(timezone.utc).weekday()
    sub1 = _make_subscription()
    sub2 = _make_subscription()

    store = MagicMock()
    store.expire_old_subscriptions = AsyncMock(return_value=0)
    store.get_active_by_day = AsyncMock(return_value=[sub1, sub2])

    worker = SubscriptionWorker(
        store=store,
        web_search=MagicMock(),
        notifier=MagicMock(),
        orchestrator=MagicMock(),
        bot_client=object(),
    )

    worker._process_subscription = AsyncMock(return_value=None)

    monkeypatch.setattr(settings, "scheduler_batch_size", 1)
    monkeypatch.setattr(settings, "scheduler_batch_delay_seconds", 0.0)

    await worker.run_daily_checks()

    store.expire_old_subscriptions.assert_awaited_once()
    store.get_active_by_day.assert_awaited_once_with(today)
    assert worker._process_subscription.await_count == 2
