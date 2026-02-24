"""Application configuration loaded from environment variables."""

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Application environment."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values can be overridden via environment variables or a .env file.
    """

    # Environment
    ENVIRONMENT: Environment = Environment.DEV

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Linear
    LINEAR_API_KEY: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""

    # Notion
    NOTION_TOKEN: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Laminar (observability)
    LAMINAR_API_KEY: str = ""

    # Sentry (error tracking)
    SENTRY_DSN: str = ""

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return the application settings (cached singleton)."""
    return Settings()
