"""
Configuration settings for the Autonomous Research Agent
Uses Pydantic for validation and environment variable loading
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


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


# Load settings from environment
settings = Settings()
