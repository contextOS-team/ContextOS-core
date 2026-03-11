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

    # Notion
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""
    NOTION_WEBHOOK_SECRET: str = ""

    # GitLab
    GITLAB_CLIENT_ID: str = ""
    GITLAB_CLIENT_SECRET: str = ""
    GITLAB_WEBHOOK_SECRET: str = ""

    # Jira
    JIRA_CLIENT_ID: str = ""
    JIRA_CLIENT_SECRET: str = ""
    JIRA_WEBHOOK_SECRET: str = ""

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

    # Telegram integration webhook secret
    # Per-workspace bot tokens stored in Vault. This secret verifies webhook authenticity.
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # Public HTTPS base URL for Telegram webhooks (e.g. ngrok URL in dev)
    TELEGRAM_WEBHOOK_BASE_URL: str = ""

    # OAuth state signing (SEC-03: dedicated secret, not provider client secrets)
    OAUTH_STATE_SECRET: str = ""

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
        return f"{self.BACKEND_URL}/api/linear/callback"

    @property
    def github_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/github/callback"

    @property
    def notion_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/notion/callback"

    @property
    def gitlab_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/gitlab/callback"

    @property
    def slack_redirect_uri(self) -> str:
        """Slack requires HTTPS — must be overridden via SLACK_REDIRECT_URI in dev."""
        if self.SLACK_REDIRECT_URI:
            return self.SLACK_REDIRECT_URI
        return f"{self.BACKEND_URL}/api/slack/callback"

    @property
    def jira_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/jira/callback"

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        """Warn about OAuth redirect URI configuration in dev."""
        if self.ENVIRONMENT != Environment.DEV:
            return

        # Slack requires HTTPS — warn if credentials are set but no redirect override
        if self.SLACK_CLIENT_ID and not self.SLACK_REDIRECT_URI:
            logger.warning(
                "Slack OAuth credentials set but SLACK_REDIRECT_URI is not configured. "
                "Slack requires HTTPS redirect URIs. "
                "Set SLACK_REDIRECT_URI to an HTTPS URL in .env."
            )

    def validate_for_production(self) -> None:
        """Fail fast if critical secrets are missing in production."""
        if self.ENVIRONMENT != Environment.PROD:
            return

        missing: list[str] = []
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.SUPABASE_JWT_SECRET:
            missing.append("SUPABASE_JWT_SECRET")
        if not self.SENTRY_DSN:
            missing.append("SENTRY_DSN")

        if not self.BACKEND_URL.startswith("https://"):
            missing.append("BACKEND_URL (must be HTTPS in production)")

        # Check each individual origin, not a substring of the whole string
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if any("localhost" in origin for origin in origins):
            missing.append("CORS_ORIGINS (contains localhost)")

        if missing:
            raise RuntimeError(
                f"Production config validation failed. Missing or invalid: {', '.join(missing)}"
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the application settings (cached singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
