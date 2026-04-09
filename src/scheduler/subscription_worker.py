"""Weekly subscription update scheduler worker."""

import asyncio
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.agents.discord_notifier import DiscordNotificationNode
from src.agents.web_search import WebSearchNode
from src.cache.subscription_store import SubscriptionStore
from src.config.settings import settings
from src.models.subscription import Subscription
from src.orchestrator import ResearchOrchestrator
from src.utils.logger import logger


def _create_scheduler_logger() -> logging.Logger:
    scheduler_logger = logging.getLogger("src.scheduler.subscription_worker")
    if scheduler_logger.handlers:
        return scheduler_logger

    scheduler_logger.setLevel(getattr(logging, settings.log_level))
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    Path("logs").mkdir(exist_ok=True)
    file_handler = RotatingFileHandler("logs/scheduler.log", maxBytes=10485760, backupCount=5)
    file_handler.setLevel(getattr(logging, settings.log_level))
    file_handler.setFormatter(formatter)

    scheduler_logger.addHandler(file_handler)
    return scheduler_logger


scheduler_logger = _create_scheduler_logger()


class SubscriptionWorker:
    """APScheduler worker for daily subscription checks."""

    def __init__(
        self,
        store: SubscriptionStore,
        web_search: WebSearchNode,
        notifier: DiscordNotificationNode,
        orchestrator: ResearchOrchestrator,
        bot_client,
    ):
        self.store = store
        self.web_search = web_search
        self.notifier = notifier
        self.orchestrator = orchestrator
        self.bot_client = bot_client
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self.scheduler.add_job(
            self.run_daily_checks,
            trigger=CronTrigger(hour=5, minute=0),
            id="subscription-daily-check",
            replace_existing=True,
        )
        self.scheduler.start()
        scheduler_logger.info("Subscription scheduler started at 05:00 UTC daily")

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            scheduler_logger.info("Subscription scheduler stopped")

    async def run_daily_checks(self) -> None:
        scheduler_logger.info("Starting daily subscription checks")
        try:
            expired_count = await self.store.expire_old_subscriptions()
            if expired_count:
                scheduler_logger.info(f"Expired {expired_count} old subscriptions")

            execution_day = datetime.now(timezone.utc).weekday()
            subscriptions = await self.store.get_active_by_day(execution_day)
            scheduler_logger.info(
                f"Found {len(subscriptions)} active subscriptions for execution_day={execution_day}"
            )

            batch_size = settings.scheduler_batch_size
            batch_delay = settings.scheduler_batch_delay_seconds

            for index in range(0, len(subscriptions), batch_size):
                batch = subscriptions[index:index + batch_size]
                await asyncio.gather(*(self._process_subscription(sub) for sub in batch))
                if index + batch_size < len(subscriptions):
                    await asyncio.sleep(batch_delay)

            scheduler_logger.info("Daily subscription checks complete")

        except Exception as exc:
            scheduler_logger.exception(f"Critical scheduler failure: {exc}")
            await self.notifier.send_admin_dm(
                f"Critical scheduler failure: {exc}",
                bot_client=self.bot_client,
            )

    async def _process_subscription(self, subscription: Subscription) -> None:
        try:
            citations = await self.web_search.search_incremental(
                subscription.topic,
                max_results=10,
                days_back=settings.update_check_days,
            )
            new_urls = [c.url for c in citations if c.url and c.url not in subscription.last_known_urls]

            if not new_urls:
                scheduler_logger.info(
                    f"No new sources for user={subscription.user_id}, topic={subscription.topic}"
                )
                return

            result = await self.orchestrator.execute(subscription.topic, notify_discord=False)
            preview = result.summary[:300] if result.summary else "New information discovered."

            embed = self.notifier.create_update_embed(
                topic=subscription.topic,
                source_count=len(new_urls),
                preview=preview,
            )
            await self.notifier.send_dm(
                user_id=subscription.user_id,
                embed=embed,
                bot_client=self.bot_client,
                topic=subscription.topic,
                orchestrator=self.orchestrator,
                subscription_store=self.store,
            )

            await self.store.update(
                subscription.user_id,
                subscription.topic,
                {
                    "last_known_urls": list({*subscription.last_known_urls, *new_urls}),
                    "last_checked": datetime.now(timezone.utc),
                },
            )

            scheduler_logger.info(
                f"Sent update to user={subscription.user_id} for topic={subscription.topic} ({len(new_urls)} new URLs)"
            )

        except Exception as exc:
            scheduler_logger.error(
                f"Subscription processing failed for user={subscription.user_id}, topic={subscription.topic}: {exc}"
            )
