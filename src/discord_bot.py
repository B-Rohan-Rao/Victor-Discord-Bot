
"""
Discord slash-command bot entrypoint.

Usage:
    uv run python -m src.discord_bot
"""

import hashlib
import os
import socket
import tempfile
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from src.agents.discord_notifier import DiscordNotificationNode
from src.agents.topic_categorizer import TopicCategorizerNode
from src.cache.subscription_store import SubscriptionStore
from src.config.settings import settings
from src.models.subscription import Subscription
from src.orchestrator import ResearchOrchestrator
from src.scheduler.subscription_worker import SubscriptionWorker
from src.utils.logger import logger

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class SingleInstanceLock:
    """File-based process lock that prevents duplicate bot instances."""

    def __init__(self, name: str = "autonomous-research-agent-bot.lock"):
        self.lock_path = os.path.join(tempfile.gettempdir(), name)
        self._handle = None

    def acquire(self) -> bool:
        self._handle = open(self.lock_path, "a+")
        try:
            if os.name == "nt":
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            return False

        self._handle.seek(0)
        self._handle.truncate(0)
        self._handle.write(str(os.getpid()))
        self._handle.flush()
        return True

    def release(self) -> None:
        if self._handle is None:
            return

        try:
            if os.name == "nt":
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None


async def safe_defer_interaction(interaction: discord.Interaction) -> bool:
    """Defer interaction safely; return False when already acknowledged."""
    try:
        await interaction.response.defer(thinking=True)
        return True
    except Exception as exc:
        # 40060 means another process/handler already acknowledged this interaction.
        if getattr(exc, "code", None) == 40060:
            logger.warning("/agent interaction already acknowledged by another handler/process")
            return False
        raise


class SubscribeView(discord.ui.View):
    """Interactive controls for topic subscription actions."""

    def __init__(self, topic: str, bot_client: "ResearchBot"):
        super().__init__(timeout=300)
        self.topic = topic
        self.bot_client = bot_client

    async def _safe_user_message(self, interaction: discord.Interaction, content: str) -> None:
        """Send ephemeral feedback even if response has already been acknowledged."""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=True)
            else:
                await interaction.response.send_message(content, ephemeral=True)
        except Exception as exc:
            logger.warning(f"Failed to send subscription feedback message: {exc}")

    async def _safe_update_view(self, interaction: discord.Interaction) -> None:
        """Update the original message view without relying on the interaction token."""
        try:
            if interaction.message is not None:
                await interaction.message.edit(view=self)
        except Exception as exc:
            logger.warning(f"Failed to update subscription view state: {exc}")

    async def _post_subscribe_tasks(self, user_id: str) -> None:
        """Run slower post-subscribe tasks without blocking button UX."""
        try:
            category = await self.bot_client.topic_categorizer.categorize(self.topic)
            await self.bot_client.subscription_store.update(
                user_id,
                self.topic,
                {"category": category},
            )
        except Exception as exc:
            logger.warning(f"Post-subscribe categorization failed for user {user_id}: {exc}")

        try:
            confirmation = self.bot_client.discord_notifier.create_subscription_result_embed(
                self.topic,
                action="subscribe",
                message=(
                    f"✅ You're now subscribed to updates for '{self.topic}'. "
                    "You'll get a DM when new information is found. Expires in 2 months."
                ),
            )
            await self.bot_client.discord_notifier.send_dm(user_id, confirmation, self.bot_client)
        except Exception as exc:
            logger.warning(f"Post-subscribe DM failed for user {user_id}: {exc}")

    @discord.ui.button(label="🔔 Subscribe to Updates", style=discord.ButtonStyle.primary)
    async def subscribe(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        user_id = str(interaction.user.id)

        try:
            # Acknowledge immediately so Discord does not expire this interaction during I/O work.
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=False)

            existing = await self.bot_client.subscription_store.get_subscription(user_id, self.topic)
            if existing is not None:
                button.label = "✅ Subscribed"
                button.disabled = True
                await self._safe_update_view(interaction)
                await self._safe_user_message(interaction, "You are already subscribed to this topic.")
                return

            current_count = await self.bot_client.subscription_store.get_count_by_user(user_id)
            if current_count >= settings.max_subscriptions_per_user:
                await self._safe_user_message(
                    interaction,
                    f"⚠️ You've reached the maximum of {settings.max_subscriptions_per_user} subscriptions. "
                    "Please unsubscribe from some topics first.",
                )
                return
            execution_day = int(hashlib.sha256(user_id.encode()).hexdigest(), 16) % 7

            now = datetime.now(timezone.utc)
            subscription = Subscription(
                user_id=user_id,
                topic=self.topic,
                category="semi-static",
                execution_day=execution_day,
                created_at=now,
                expires_at=now + timedelta(days=settings.subscription_expiry_days),
                status="active",
            )

            create_status = await self.bot_client.subscription_store.create(subscription)

            if create_status == "already_active":
                button.label = "✅ Subscribed"
                button.disabled = True
                await self._safe_update_view(interaction)
                await self._safe_user_message(interaction, "You are already subscribed to this topic.")
                return

            if create_status == "failed":
                await self._safe_user_message(interaction, "I could not create a new subscription for this topic.")
                return

            button.label = "✅ Subscribed"
            button.disabled = True
            await self._safe_update_view(interaction)

            asyncio.create_task(self._post_subscribe_tasks(user_id))
            if create_status == "reactivated":
                await self._safe_user_message(interaction, "Subscription re-activated. Check your DMs for confirmation.")
            else:
                await self._safe_user_message(interaction, "Subscription saved. Check your DMs for confirmation.")
        except Exception as exc:
            logger.error(f"Subscribe action failed for user {user_id}: {exc}")
            await self._safe_user_message(interaction, "Subscription failed. Please try again shortly.")

    @discord.ui.button(label="❌ Unsubscribe", style=discord.ButtonStyle.secondary)
    async def unsubscribe(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        user_id = str(interaction.user.id)
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=False)

            removed = await self.bot_client.subscription_store.delete(user_id, self.topic)
            if removed:
                confirmation = self.bot_client.discord_notifier.create_subscription_result_embed(
                    self.topic,
                    action="unsubscribe",
                    message=f"✅ Unsubscribed from '{self.topic}'. You can re-subscribe anytime.",
                )
                await self.bot_client.discord_notifier.send_dm(user_id, confirmation, self.bot_client)
                await self._safe_user_message(interaction, f"✅ Unsubscribed from '{self.topic}'.")
            else:
                await self._safe_user_message(interaction, "No active subscription found for this topic.")
        except Exception as exc:
            logger.error(f"Unsubscribe action failed for user {user_id}: {exc}")
            await self._safe_user_message(interaction, "Unsubscribe failed. Please try again shortly.")


class ResearchBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.orchestrator = ResearchOrchestrator()
        self.discord_notifier = DiscordNotificationNode()
        self.subscription_store = SubscriptionStore()
        self.topic_categorizer = TopicCategorizerNode(self.orchestrator.llm)
        self.subscription_worker: SubscriptionWorker | None = None

    async def setup_hook(self) -> None:
        # Ensure typo legacy command is removed on sync.
        self.tree.remove_command("heath")
        if settings.discord_guild_id:
            guild = discord.Object(id=int(settings.discord_guild_id))
            self.tree.remove_command("heath", guild=guild)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced slash commands to guild {settings.discord_guild_id}")
        else:
            await self.tree.sync()
            logger.info("Synced global slash commands")

        self.subscription_worker = SubscriptionWorker(
            store=self.subscription_store,
            web_search=self.orchestrator.web_search,
            notifier=self.discord_notifier,
            orchestrator=self.orchestrator,
            bot_client=self,
        )
        self.subscription_worker.start()

    async def close(self) -> None:
        if self.subscription_worker is not None:
            await self.subscription_worker.stop()
        await self.subscription_store.close()
        await super().close()


bot = ResearchBot()


@bot.tree.command(name="agent", description="Run autonomous research on a question")
@app_commands.describe(question="What do you want the research agent to investigate?")
async def agent(interaction: discord.Interaction, question: str) -> None:
    if not await safe_defer_interaction(interaction):
        return

    try:
        # Slash command already sends a direct response; disable webhook duplicate posts.
        result = await bot.orchestrator.execute(question, notify_discord=False)

        embed = discord.Embed(
            title="Research Result",
            description=f"**Query:** {result.query}",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Summary",
            value=(result.summary[:1000] + "...") if len(result.summary) > 1000 else result.summary,
            inline=False,
        )
        embed.add_field(name="Confidence", value=f"{result.confidence_score * 100:.0f}%", inline=True)
        embed.add_field(name="Sources", value=str(len(result.all_sources)), inline=True)

        if result.hallucination_flags:
            flags = "\n".join(result.hallucination_flags[:3])
            embed.add_field(name="Flags", value=flags[:1000], inline=False)

        view = SubscribeView(topic=question, bot_client=bot)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as exc:
        logger.error(f"Slash command /agent failed: {exc}")
        await interaction.followup.send("I ran into an error while researching that question.")


async def _send_health(interaction: discord.Interaction) -> None:
    """Operational health snapshot for quick diagnostics."""
    scheduler_running = bool(
        bot.subscription_worker is not None and bot.subscription_worker.scheduler.running
    )

    mongo_ok = "configured" if bool(settings.mongo_uri) else "missing"
    redis_ok = "configured" if bool(settings.redis_host) else "missing"
    runtime_name = settings.bot_instance_name or ("RAILWAY" if os.getenv("RAILWAY_PROJECT_ID") else "LOCAL")
    runtime_identity = f"{runtime_name} @ {socket.gethostname()}"

    embed = discord.Embed(
        title="Bot Health",
        description="Current runtime status for core components.",
        color=discord.Color.green() if scheduler_running else discord.Color.orange(),
    )
    embed.add_field(name="Discord", value="connected" if bot.is_ready() else "not ready", inline=True)
    embed.add_field(name="Scheduler", value="running" if scheduler_running else "stopped", inline=True)
    embed.add_field(name="Guild Sync", value=settings.discord_guild_id or "global", inline=True)
    embed.add_field(name="Mongo", value=mongo_ok, inline=True)
    embed.add_field(name="Redis", value=redis_ok, inline=True)
    embed.add_field(name="Runtime", value=runtime_identity, inline=False)
    embed.add_field(
        name="Limits",
        value=(
            f"max_subscriptions={settings.max_subscriptions_per_user}\n"
            f"expiry_days={settings.subscription_expiry_days}\n"
            f"batch={settings.scheduler_batch_size}/{settings.scheduler_batch_delay_seconds}s"
        ),
        inline=False,
    )
    embed.add_field(
        name="Token Safety",
        value="Run only one runtime for this bot token (local or Railway, not both).",
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="health", description="Show bot and scheduler health status")
async def health(interaction: discord.Interaction) -> None:
    await _send_health(interaction)


def main() -> None:
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing in .env")

    lock = SingleInstanceLock()
    if not lock.acquire():
        logger.error("Another bot instance is already running. Exiting to prevent duplicate Discord interaction handling.")
        raise SystemExit(1)

    try:
        bot.run(settings.discord_bot_token)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
