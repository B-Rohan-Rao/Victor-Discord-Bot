"""
Configuration settings for the Autonomous Research Agent
Uses Pydantic for validation and environment variable loading
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Groq LLM Configuration
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY", description="Groq API key for LLM access")
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        validation_alias="GROQ_MODEL",
        description="Groq model identifier"
    )
    serper_api_key: str = Field(
        default="",
        validation_alias="SERPER_API_KEY",
        description="Serper API key for Google search"
    )

    # Cache Configuration
    cache_ttl: int = Field(
        default=2592000,  # 30 days
        validation_alias="CACHE_TTL",
        description="Cache time-to-live in seconds"
    )

    # Redis Configuration (primary fast cache)
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")

    # MongoDB Configuration (persistent backing store)
    mongo_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias="MONGO_URI",
        description="MongoDB connection URI"
    )
    mongo_database: str = Field(
        default="autonomous_research_agent",
        validation_alias="MONGO_DATABASE",
        description="MongoDB database name"
    )
    mongo_collection: str = Field(
        default="research_results",
        validation_alias="MONGO_COLLECTION",
        description="MongoDB collection for research results"
    )

    # Discord Webhook
    discord_webhook_url: str = Field(default="", validation_alias="DISCORD_WEBHOOK_URL")
    discord_bot_token: str = Field(default="", validation_alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str = Field(default="", validation_alias="DISCORD_GUILD_ID")

    # Web Scraping Configuration
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        validation_alias="USER_AGENT"
    )
    request_timeout: int = Field(default=10, validation_alias="REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, validation_alias="MAX_RETRIES")

    # Search Configuration
    max_search_results: int = Field(default=5, validation_alias="MAX_SEARCH_RESULTS")
    preferred_sources: str = Field(
        default="academic,news,official",
        validation_alias="PREFERRED_SOURCES"
    )

    # Application Configuration
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    debug_mode: bool = Field(default=False, validation_alias="DEBUG_MODE")
    max_concurrent_queries: int = Field(default=5, validation_alias="MAX_CONCURRENT_QUERIES")
    hallucination_threshold: float = Field(
        default=0.75,
        validation_alias="HALLUCINATION_THRESHOLD",
        description="Confidence threshold for flagging hallucinations (0-1)"
    )

    # Subscription/Scheduler configuration
    max_subscriptions_per_user: int = Field(default=20, validation_alias="MAX_SUBSCRIPTIONS_PER_USER")
    subscription_expiry_days: int = Field(default=60, validation_alias="SUBSCRIPTION_EXPIRY_DAYS")
    scheduler_batch_size: int = Field(default=20, validation_alias="SCHEDULER_BATCH_SIZE")
    scheduler_batch_delay_seconds: float = Field(
        default=3.0,
        validation_alias="SCHEDULER_BATCH_DELAY_SECONDS",
    )
    admin_user_id: str = Field(default="", validation_alias="ADMIN_USER_ID")
    update_check_days: int = Field(default=7, validation_alias="UPDATE_CHECK_DAYS")
    bot_instance_name: str = Field(default="", validation_alias="BOT_INSTANCE_NAME")

    @property
    def preferred_sources_list(self) -> list[str]:
        """Parse preferred sources from config"""
        return [s.strip() for s in self.preferred_sources.split(",")]

    @property
    def groq_model_name(self) -> str:
        """Return model name in Groq-compatible format.

        Accepts either:
        - llama-3.1-8b-instant
        - groq/llama-3.1-8b-instant
        """
        model = self.groq_model.strip()
        if model.startswith("groq/"):
            return model.split("/", 1)[1]
        return model

    @staticmethod
    def _normalize_secret(value: str) -> str:
        """Trim whitespace and surrounding quotes from secret values."""
        normalized = (value or "").strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in ('"', "'"):
            normalized = normalized[1:-1].strip()
        return normalized

    @property
    def groq_api_key_value(self) -> str:
        """Return normalized GROQ API key, with env fallback for hosted runtimes."""
        return self._normalize_secret(self.groq_api_key or os.getenv("GROQ_API_KEY", ""))

    @property
    def discord_bot_token_value(self) -> str:
        """Return normalized Discord bot token, with env fallback for hosted runtimes."""
        return self._normalize_secret(self.discord_bot_token or os.getenv("DISCORD_BOT_TOKEN", ""))


# Load settings from environment
settings = Settings()
