"""Centralized LLM client with Laminar observability tracing.

All LLM calls in ContextOS go through this client so that every call is
automatically traced in Laminar with prompt, response, latency, and token
counts.  The client uses the Google Gemini SDK.

Context generation consumes ``LLMClient`` directly -- no additional
observability wiring needed by callers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from google import genai
from google.genai import types

from src.observability.laminar import observe, set_laminar_metadata

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Structured response from an LLM generation call.

    Captures everything needed for observability and cost tracking.
    """

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    model: str


class LLMClient:
    """Laminar-instrumented wrapper around Google Gemini.

    All generation methods are decorated with ``@observe`` so Laminar
    automatically records prompt, response, latency, and token counts
    when the SDK is initialized.

    Args:
        model_name: Gemini model identifier.  Defaults to ``gemini-3.1-flash-lite-preview``.
    """

    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite-preview",
    ) -> None:
        self.model_name = model_name
        from src.config import get_settings
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @observe(name="llm_generate")
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        workspace_id: UUID | None = None,
        ticket_identifier: str | None = None,
    ) -> LLMResponse:
        """Generate a response from the Gemini model.

        Args:
            prompt: User/content prompt to send.
            system_prompt: Optional system instruction for the model.
            workspace_id: Workspace UUID to tag on the Laminar trace.
            ticket_identifier: Human-readable ticket ref (e.g. ``ENG-42``).

        Returns:
            An ``LLMResponse`` with text, token counts, latency, and model name.

        Raises:
            Exception: Propagates any Gemini errors (auth, quota, etc.)
                so callers can handle them explicitly.
        """
        if workspace_id is not None or ticket_identifier is not None:
            set_laminar_metadata(
                workspace_id=str(workspace_id) if workspace_id else None,
                ticket_identifier=ticket_identifier,
            )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )

        start = time.monotonic()

        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Extract token counts from usage metadata.
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0
        total_tokens = usage.total_token_count if usage else 0

        text = response.text or ""

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=round(elapsed_ms, 2),
            model=self.model_name,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return a cached singleton ``LLMClient`` instance.

    The client is lazily created on first call so that import-time side
    effects are avoided.
    """
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
