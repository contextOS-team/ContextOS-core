"""Application configuration loaded from environment variables."""

import logging
from enum import Enum

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Graph-enhanced retrieval constants
CONTEXT_TOKEN_BUDGET = 5000  # Unified token budget for all retrieval signals
GRAPH_MAX_DEPTH = 2          # Maximum traversal depth for graph signal


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

    # Langfuse (observability)
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Sentry (error tracking)
    SENTRY_DSN: str = ""

    # Telegram (critical error alerts via Sentry webhook)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Phase 40: shared-bot integration secrets. The webhook secret verifies the
    # X-Telegram-Bot-Api-Secret-Token header on the global webhook; the base URL
    # is the public HTTPS endpoint Telegram POSTs to (override via ngrok in dev).
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_WEBHOOK_BASE_URL: str = ""
    # Shared @ContextOSBot token (replaces per-workspace BotFather tokens).
    # Distinct from TELEGRAM_BOT_TOKEN above (Sentry alerts) -- DO NOT collapse them.
    TELEGRAM_BOT_TOKEN_GLOBAL: str = ""
    # Shared bot username, used to render `https://t.me/<username>?startgroup=<code>`
    # deep links and to strip `/start@<username>` suffixes during claim parsing.
    TELEGRAM_BOT_USERNAME: str = ""

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

        # Hosted Supabase projects can sign access tokens with asymmetric
        # keys. Those tokens are verified through the project's public JWKS,
        # so the legacy shared JWT secret is intentionally optional.
        if not self.SUPABASE_URL.startswith("https://"):
            missing.append("SUPABASE_URL (must be HTTPS in production)")
        if not self.SUPABASE_ANON_KEY:
            missing.append("SUPABASE_ANON_KEY")

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
