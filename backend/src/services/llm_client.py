"""Centralized LLM client with Laminar observability tracing.

All LLM calls in ContextOS go through this client so that every call is
automatically traced in Laminar with prompt, response, latency, and token
counts.  The client uses the Google GenAI SDK (``google-genai``) to call
Gemini models.

Phase 4 (Context Generation) will consume ``LLMClient`` directly -- no
additional observability wiring needed by callers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from google import genai
from google.genai.types import GenerateContentConfig

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
    """Laminar-instrumented wrapper around Google GenAI (Gemini).

    All generation methods are decorated with ``@observe`` so Laminar
    automatically records prompt, response, latency, and token counts
    when the SDK is initialized.

    Args:
        model_name: Gemini model identifier.  Defaults to ``gemini-3-flash-preview``.
    """

    def __init__(
        self,
        model_name: str = "gemini-3-flash-preview",
    ) -> None:
        self.model_name = model_name
        # google-genai Client reads API key from GEMINI_API_KEY env var.
        self._client = genai.Client()

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
            Exception: Propagates any Google GenAI errors (auth, quota, etc.)
                so callers can handle them explicitly.
        """
        if workspace_id is not None or ticket_identifier is not None:
            set_laminar_metadata(
                workspace_id=str(workspace_id) if workspace_id else None,
                ticket_identifier=ticket_identifier,
            )

        config = GenerateContentConfig(
            system_instruction=system_prompt,
        ) if system_prompt else None

        start = time.monotonic()

        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Extract token counts from usage metadata.
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count or 0 if usage else 0
        completion_tokens = usage.candidates_token_count or 0 if usage else 0
        total_tokens = usage.total_token_count or 0 if usage else 0

        text = response.text or ""

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=round(elapsed_ms, 2),
            model=self.model_name,
        )

    @observe(name="llm_generate_with_context")
    async def generate_context_page(
        self,
        ticket_data: dict,
        sources: list[dict],
        workspace_id: UUID,
        ticket_identifier: str,
    ) -> LLMResponse:
        """Generate a context page from ticket data and related sources.

        Builds a synthesis prompt from the provided data and calls
        :meth:`generate`.  Phase 4 will refine the prompt template;
        this is a working placeholder.

        Args:
            ticket_data: Dict with ticket fields (title, description, etc.).
            sources: List of source dicts (Slack messages, meeting excerpts, etc.).
            workspace_id: Workspace UUID for trace tagging.
            ticket_identifier: Human-readable ticket reference.

        Returns:
            ``LLMResponse`` from the synthesis call.
        """
        # Build synthesis prompt -- Phase 4 will provide the real template.
        source_texts = "\n\n".join(
            f"### Source: {s.get('type', 'unknown')}\n{s.get('content', '')}"
            for s in sources
        )

        prompt = (
            f"You are a context synthesis assistant for engineering tickets.\n\n"
            f"## Ticket: {ticket_data.get('identifier', ticket_identifier)}\n"
            f"**Title:** {ticket_data.get('title', 'Untitled')}\n"
            f"**Description:** {ticket_data.get('description', 'No description')}\n\n"
            f"## Related Sources\n{source_texts}\n\n"
            f"Synthesize the above into a concise context page that helps an "
            f"engineer understand the full story behind this ticket."
        )

        system_prompt = (
            "You are a technical writing assistant. Produce clear, concise "
            "context summaries for engineering teams. Focus on decisions, "
            "requirements, and actionable information."
        )

        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            workspace_id=workspace_id,
            ticket_identifier=ticket_identifier,
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
