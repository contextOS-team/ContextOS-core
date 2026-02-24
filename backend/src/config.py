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

    # Google Gemini
    GOOGLE_GENAI_API_KEY: str = ""

    # Linear
    LINEAR_API_KEY: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Laminar (observability)
    LAMINAR_API_KEY: str = ""

    # Sentry (error tracking)
    SENTRY_DSN: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Backend URL
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Split CORS_ORIGINS by comma into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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
