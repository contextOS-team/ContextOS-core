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

    # Database (async PostgreSQL connection string)
    DATABASE_URL: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Google Gemini (SDK reads from GEMINI_API_KEY env var automatically)
    GEMINI_API_KEY: str = ""

    # Linear
    LINEAR_API_KEY: str = ""
    LINEAR_CLIENT_ID: str = ""
    LINEAR_CLIENT_SECRET: str = ""
    LINEAR_WEBHOOK_SECRET: str = ""
    LINEAR_REDIRECT_URI: str = ""

    # Slack
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_REDIRECT_URI: str = ""
    SLACK_BOT_TOKEN: str = ""

    # GitHub App
    GITHUB_APP_ID: str = ""
    GITHUB_APP_SLUG: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_REDIRECT_URI: str = ""

    # Fathom
    FATHOM_API_KEY: str = ""
    FATHOM_API_BASE_URL: str = "https://api.fathom.ai/external/v1"

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Laminar (observability)
    LAMINAR_API_KEY: str = ""

    # Sentry (error tracking)
    SENTRY_DSN: str = ""

    # Telegram (critical error alerts via Sentry webhook)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Backend URL
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Split CORS_ORIGINS by comma into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def linear_redirect_uri(self) -> str:
        """Return the Linear OAuth redirect URI.

        Uses LINEAR_REDIRECT_URI if set, otherwise defaults to
        {BACKEND_URL}/api/linear/callback.
        """
        if self.LINEAR_REDIRECT_URI:
            return self.LINEAR_REDIRECT_URI
        return f"{self.BACKEND_URL}/api/linear/callback"

    @property
    def github_redirect_uri(self) -> str:
        """Return the GitHub OAuth redirect URI.

        Uses GITHUB_REDIRECT_URI if set, otherwise defaults to
        {BACKEND_URL}/api/github/callback.
        """
        if self.GITHUB_REDIRECT_URI:
            return self.GITHUB_REDIRECT_URI
        return f"{self.BACKEND_URL}/api/github/callback"

    @property
    def slack_redirect_uri(self) -> str:
        """Return the Slack OAuth redirect URI.

        Uses SLACK_REDIRECT_URI if set, otherwise defaults to
        {BACKEND_URL}/api/slack/callback.
        """
        if self.SLACK_REDIRECT_URI:
            return self.SLACK_REDIRECT_URI
        return f"{self.BACKEND_URL}/api/slack/callback"

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
