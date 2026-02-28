"""Application configuration loaded from environment variables."""

import logging
from enum import Enum

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


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
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Google Gemini (SDK reads from GEMINI_API_KEY env var automatically)
    GEMINI_API_KEY: str = ""

    # OpenAI (for embeddings via text-embedding-3-small)
    OPENAI_API_KEY: str = ""

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

    # Notion
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""
    NOTION_REDIRECT_URI: str = ""
    NOTION_WEBHOOK_SECRET: str = ""

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

    # ngrok (optional — used to build OAuth redirect URIs in local dev)
    NGROK_DOMAIN: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Split CORS_ORIGINS by comma into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def _public_base_url(self) -> str:
        """Return the public-facing base URL.

        Uses NGROK_DOMAIN if set (for OAuth callbacks that need a public URL),
        otherwise falls back to BACKEND_URL.
        """
        if self.NGROK_DOMAIN:
            return f"https://{self.NGROK_DOMAIN}"
        return self.BACKEND_URL

    @property
    def linear_redirect_uri(self) -> str:
        if self.LINEAR_REDIRECT_URI:
            return self.LINEAR_REDIRECT_URI
        return f"{self._public_base_url}/api/linear/callback"

    @property
    def github_redirect_uri(self) -> str:
        if self.GITHUB_REDIRECT_URI:
            return self.GITHUB_REDIRECT_URI
        return f"{self._public_base_url}/api/github/callback"

    @property
    def notion_redirect_uri(self) -> str:
        if self.NOTION_REDIRECT_URI:
            return self.NOTION_REDIRECT_URI
        return f"{self._public_base_url}/api/notion/callback"

    @property
    def slack_redirect_uri(self) -> str:
        if self.SLACK_REDIRECT_URI:
            return self.SLACK_REDIRECT_URI
        return f"{self._public_base_url}/api/slack/callback"

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        """Warn when OAuth credentials are configured but NGROK_DOMAIN is empty."""
        oauth_providers = {
            "Linear": self.LINEAR_CLIENT_ID,
            "Slack": self.SLACK_CLIENT_ID,
            "GitHub": self.GITHUB_CLIENT_ID,
            "Notion": self.NOTION_CLIENT_ID,
        }
        configured = [name for name, val in oauth_providers.items() if val]
        if configured and not self.NGROK_DOMAIN:
            logger.warning(
                "OAuth credentials set for %s but NGROK_DOMAIN is empty. "
                "Redirect URIs will point to localhost and OAuth flows will fail. "
                "Set NGROK_DOMAIN in .env or run `make dev-ngrok`.",
                ", ".join(configured),
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the application settings (cached singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
