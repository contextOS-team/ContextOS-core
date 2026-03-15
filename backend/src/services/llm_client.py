"""Centralized LLM client with Laminar + Langfuse observability tracing.

All LLM calls in ContextOS go through this client so that every call is
automatically traced with prompt, response, latency, and token counts.
The client uses the Google Gemini SDK.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from google import genai
from google.genai import types

from src.observability.laminar import observe, set_laminar_metadata
from src.observability.langfuse_client import langfuse_observe, update_langfuse_trace

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
        model_name: str = "gemini-3.1-flash-lite-preview",
    ) -> None:
        self.model_name = model_name
        from src.config import get_settings
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @langfuse_observe(name="llm_generate")
    @observe(name="llm_generate")
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        workspace_id: UUID | None = None,
        ticket_identifier: str | None = None,
    ) -> LLMResponse:
        """Generate a response from the Gemini model."""
        if workspace_id is not None or ticket_identifier is not None:
            set_laminar_metadata(
                workspace_id=str(workspace_id) if workspace_id else None,
                ticket_identifier=ticket_identifier,
            )

        # Update Langfuse trace with input and metadata
        update_langfuse_trace(
            name=f"context_synthesis:{ticket_identifier or 'unknown'}",
            input={"prompt": prompt[:500], "system_prompt": system_prompt[:200] if system_prompt else None, "model": self.model_name},
            metadata={
                "workspace_id": str(workspace_id) if workspace_id else None,
                "ticket_identifier": ticket_identifier,
                "model": self.model_name,
            },
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

        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0
        total_tokens = usage.total_token_count if usage else 0

        text = response.text or ""

        # Update Langfuse trace with output
        update_langfuse_trace(
            output={
                "text": text[:500],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": round(elapsed_ms, 2),
            },
        )

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
    """Return a cached singleton ``LLMClient`` instance."""
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
