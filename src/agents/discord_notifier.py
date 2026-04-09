"""
Discord Integration for Report Delivery
Sends research reports as formatted Discord embeds with Gen-Z vibes
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING
import discord
from discord_webhook import DiscordWebhook, DiscordEmbed
from src.models.research import ResearchResult, ClaimWithCitation, Citation
from src.utils.logger import logger
from src.config.settings import settings
from datetime import datetime

if TYPE_CHECKING:
    from src.cache.subscription_store import SubscriptionStore
    from src.orchestrator import ResearchOrchestrator


class UpdateActionsView(discord.ui.View):
    """Buttons attached to weekly DM update notifications."""

    def __init__(
        self,
        topic: str,
        orchestrator: "ResearchOrchestrator",
        subscription_store: "SubscriptionStore",
    ):
        super().__init__(timeout=86400)
        self.topic = topic
        self.orchestrator = orchestrator
        self.subscription_store = subscription_store

    @discord.ui.button(label="View Full Update", style=discord.ButtonStyle.primary)
    async def view_full_update(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer(thinking=True)
        try:
            result = await self.orchestrator.execute(self.topic, notify_discord=False)
            embed = discord.Embed(
                title=f"Full Update: {self.topic[:200]}",
                description=(result.summary[:1000] + "...") if len(result.summary) > 1000 else result.summary,
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Confidence", value=f"{result.confidence_score * 100:.0f}%", inline=True)
            embed.add_field(name="Sources", value=str(len(result.all_sources)), inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            logger.error(f"Failed to run full update for topic '{self.topic}': {exc}")
            await interaction.followup.send("I could not run a full refresh right now.")

    @discord.ui.button(label="❌ Unsubscribe", style=discord.ButtonStyle.danger)
    async def unsubscribe(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        removed = await self.subscription_store.delete(str(interaction.user.id), self.topic)
        if removed:
            await interaction.response.send_message(
                f"✅ Unsubscribed from '{self.topic}'. You can re-subscribe anytime.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "I could not find an active subscription for this topic.",
                ephemeral=True,
            )


class DiscordNotificationNode:
    """
    Sends formatted research reports to Discord
    Creates eye-catching embeds with emojis and colors
    Gen-Z friendly formatting
    """

    def __init__(self):
        self.webhook_url = settings.discord_webhook_url

    async def send_report(self, result: ResearchResult) -> bool:
        """
        Send research result to Discord as formatted embed
        """
        if not self.webhook_url:
            logger.warning("Discord webhook not configured")
            return False

        try:
            webhook = DiscordWebhook(url=self.webhook_url)

            # Main embed
            embed = DiscordEmbed(
                title=f"🔥 Research Just Dropped 🔥",
                description=f"**Query:** {result.query}",
                color="FF6B9D"  # Pink Gen-Z vibes
            )

            # Summary section
            embed.add_embed_field(
                name="💡 Key Findings",
                value=result.summary[:500] + ("..." if len(result.summary) > 500 else ""),
                inline=False
            )

            # Claims section with citations
            if result.claims:
                claims_text = "\\n".join([
                    f"• {claim.claim}"
                    for claim in result.claims[:3]
                ])
                embed.add_embed_field(
                    name="📍 Top Claims",
                    value=claims_text[:300] + ("..." if len(claims_text) > 300 else ""),
                    inline=False
                )

            # Sources section
            if result.all_sources:
                sources_text = "\\n".join([
                    f"[{source.title[:40]}]({source.url})"
                    for source in result.all_sources[:3]
                ])
                embed.add_embed_field(
                    name="📚 Sources",
                    value=sources_text,
                    inline=False
                )

            # Confidence score
            confidence_emoji = "✨" if result.confidence_score > 0.8 else "⚠️"
            embed.add_embed_field(
                name=f"{confidence_emoji} Confidence",
                value=f"{result.confidence_score * 100:.0f}%",
                inline=True
            )

            # Hallucination flags
            if result.hallucination_flags:
                flags_text = "\\n".join(result.hallucination_flags[:3])
                embed.add_embed_field(
                    name="🚩 Flags",
                    value=flags_text,
                    inline=True
                )
            else:
                embed.add_embed_field(
                    name="✅ Status",
                    value="No issues detected",
                    inline=True
                )

            # Footer with timestamp
            embed.set_footer(text=f"Research completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            embed.set_timestamp()

            webhook.add_embed(embed)
            webhook.execute()

            logger.info(f"Discord notification sent for query: {result.query}")
            return True

        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False

    async def send_error_report(self, query: str, error: str) -> bool:
        """
        Send error notification to Discord
        """
        if not self.webhook_url:
            return False

        try:
            webhook = DiscordWebhook(url=self.webhook_url)

            embed = DiscordEmbed(
                title="⚠️ Research Error",
                description=f"Query: {query}",
                color="FF0000"  # Red error color
            )

            embed.add_embed_field(
                name="Error Details",
                value=error[:500],
                inline=False
            )

            webhook.add_embed(embed)
            webhook.execute()

            return True

        except Exception as e:
            logger.error(f"Error sending error report to Discord: {e}")
            return False

    def create_update_embed(self, topic: str, source_count: int, preview: str) -> discord.Embed:
        """Create the weekly update embed payload."""
        embed = discord.Embed(
            title=f"📬 Weekly Update: {topic[:200]}",
            description=f"New since last week: {source_count} source(s) found",
            color=discord.Color.green(),
        )
        embed.add_field(name="Preview", value=preview[:300] if preview else "No preview available", inline=False)
        embed.set_footer(text="Use the buttons below to refresh or unsubscribe.")
        return embed

    def create_subscription_result_embed(self, topic: str, action: str, message: str) -> discord.Embed:
        """Create confirmation embeds for subscribe/unsubscribe actions."""
        color = discord.Color.green() if action == "subscribe" else discord.Color.orange()
        embed = discord.Embed(
            title="Subscription Updated",
            description=message,
            color=color,
        )
        embed.add_field(name="Topic", value=topic[:1024], inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        return embed

    async def send_dm(
        self,
        user_id: str,
        embed: discord.Embed,
        bot_client: discord.Client,
        topic: str | None = None,
        orchestrator: "ResearchOrchestrator" | None = None,
        subscription_store: "SubscriptionStore" | None = None,
    ) -> bool:
        """Send a DM embed to a user by ID."""
        try:
            user = bot_client.get_user(int(user_id))
            if user is None:
                user = await bot_client.fetch_user(int(user_id))

            if user is None:
                logger.warning(f"Unable to resolve user for DM: {user_id}")
                return False

            view = None
            if topic and orchestrator and subscription_store:
                view = UpdateActionsView(topic, orchestrator, subscription_store)

            await user.send(embed=embed, view=view)
            return True
        except Exception as exc:
            logger.error(f"Failed to send DM to user {user_id}: {exc}")
            return False

    async def send_admin_dm(self, message: str, bot_client: discord.Client) -> bool:
        """Send critical scheduler failures to the configured admin user."""
        if not settings.admin_user_id:
            logger.warning("ADMIN_USER_ID is not configured; skipping admin DM")
            return False

        embed = discord.Embed(
            title="⚠️ Scheduler Alert",
            description=message[:1800],
            color=discord.Color.red(),
        )
        return await self.send_dm(settings.admin_user_id, embed, bot_client)
