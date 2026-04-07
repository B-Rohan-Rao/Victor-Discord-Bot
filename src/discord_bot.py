
"""
Discord slash-command bot entrypoint.

Usage:
    uv run python -m src.discord_bot
"""

import discord
from discord import app_commands

from src.config.settings import settings
from src.orchestrator import ResearchOrchestrator
from src.utils.logger import logger


class ResearchBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.orchestrator = ResearchOrchestrator()

    async def setup_hook(self) -> None:
        if settings.discord_guild_id:
            guild = discord.Object(id=int(settings.discord_guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced slash commands to guild {settings.discord_guild_id}")
        else:
            await self.tree.sync()
            logger.info("Synced global slash commands")


bot = ResearchBot()


@bot.tree.command(name="agent", description="Run autonomous research on a question")
@app_commands.describe(question="What do you want the research agent to investigate?")
async def agent(interaction: discord.Interaction, question: str) -> None:
    await interaction.response.defer(thinking=True)

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

        await interaction.followup.send(embed=embed)
    except Exception as exc:
        logger.error(f"Slash command /agent failed: {exc}")
        await interaction.followup.send("I ran into an error while researching that question.")


def main() -> None:
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing in .env")

    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    main()
