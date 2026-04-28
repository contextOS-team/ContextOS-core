"""Centralized LLM client with Laminar + Langfuse observability tracing.

All LLM calls in ContextOS go through this client so that every call is
automatically traced with prompt, response, latency, and token counts.
The client uses the Google Gemini SDK.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

from src.observability.laminar import observe, set_laminar_metadata
from src.observability.langfuse_client import langfuse_observe, update_generation

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Structured response from an LLM generation call."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    model: str


class LLMClient:
    """Instrumented wrapper around Google Gemini with Laminar + Langfuse tracing."""

    def __init__(
        self,
        model_name: str = "gemini-3.0-flash",
    ) -> None:
        self.model_name = model_name
        from src.config import get_settings
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def _call_gemini(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
    ) -> tuple[str, int, int, int, float]:
        """Shared Gemini call with timing and observability.

        Returns (text, prompt_tokens, completion_tokens, total_tokens, elapsed_ms).
        """
        start = time.monotonic()

        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0
        total_tokens = usage.total_token_count if usage else 0

        text = response.text or ""

        update_generation(
            model=self.model_name,
            usage={
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": total_tokens,
            },
            output=text[:1000],
        )

        return text, prompt_tokens, completion_tokens, total_tokens, elapsed_ms

    @langfuse_observe(name="llm_generate", as_type="generation")
    @observe(name="llm_generate")
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        workspace_id: UUID | None = None,
        ticket_identifier: str | None = None,
    ) -> LLMResponse:
        """Generate a response from the Gemini model.

        ``temperature`` is optional; when omitted Gemini's model default applies.
        """
        if workspace_id is not None or ticket_identifier is not None:
            set_laminar_metadata(
                workspace_id=str(workspace_id) if workspace_id else None,
                ticket_identifier=ticket_identifier,
            )

        config_kwargs: dict[str, object] = {"system_instruction": system_prompt}
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        config = types.GenerateContentConfig(**config_kwargs)

        text, prompt_tokens, completion_tokens, total_tokens, elapsed_ms = (
            await self._call_gemini(prompt, config)
        )

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=round(elapsed_ms, 2),
            model=self.model_name,
        )

    @langfuse_observe(name="llm_generate_json", as_type="generation")
    @observe(name="llm_generate_json")
    async def generate_json(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        workspace_id: UUID | None = None,
    ) -> T:
        """Generate a structured JSON response conforming to a Pydantic schema.

        Uses Gemini's response_mime_type + response_schema for guaranteed
        JSON conformance. Raises on failure — callers handle fallback.
        """
        if workspace_id is not None:
            set_laminar_metadata(workspace_id=str(workspace_id))

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
        )

        raw_text, _, _, total_tokens, elapsed_ms = (
            await self._call_gemini(prompt, config)
        )

        logger.debug(
            "generate_json: %d tokens in %.0fms",
            total_tokens, elapsed_ms,
        )

        return schema.model_validate_json(raw_text)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return a cached singleton ``LLMClient`` instance."""
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
