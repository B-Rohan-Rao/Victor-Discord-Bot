"""
Discord Integration for Report Delivery
Sends research reports as formatted Discord embeds with Gen-Z vibes
"""

from typing import List
from discord_webhook import DiscordWebhook, DiscordEmbed
from src.models.research import ResearchResult, ClaimWithCitation, Citation
from src.utils.logger import logger
from src.config.settings import settings
from datetime import datetime


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
