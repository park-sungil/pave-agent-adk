"""Centralized LLM access for pave_agent.

Single source of truth for:
- How the orchestrator's ADK LiteLlm wrapper is constructed
- How analyze/interpret tools make direct litellm.completion calls
- Which auth method is used (api_key vs custom header)
- The vLLM content-field compatibility patch

Auth methods (switch via settings.LLM_AUTH_METHOD):
- "key"    → passes api_key (standard OpenAI-compatible auth)
- "header" → passes extra_headers={HEADER_NAME: HEADER_VALUE}

Both methods always pass `model` and `api_base`.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm
from google.adk.models.lite_llm import LiteLlm
from litellm.integrations.custom_logger import CustomLogger

from pave_agent import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# vLLM compatibility patch
# ---------------------------------------------------------------------------

class _FixAssistantContent(CustomLogger):
    """Our internal vLLM server rejects assistant messages that omit the
    `content` field when tool_calls are present (422 Unprocessable Entity).
    Set content=None in place before the request is sent.
    """

    def log_pre_api_call(self, model, messages, kwargs):  # noqa: D401
        for msg in messages:
            if msg.get("role") == "assistant" and "content" not in msg:
                msg["content"] = None


def _ensure_patch_registered() -> None:
    # Name-based check so module reloads don't double-register even though
    # the class identity changes after reload.
    if not any(type(cb).__name__ == "_FixAssistantContent" for cb in litellm.callbacks):
        litellm.callbacks.append(_FixAssistantContent())


_ensure_patch_registered()


# ---------------------------------------------------------------------------
# Common kwargs builder
# ---------------------------------------------------------------------------

def _auth_kwargs() -> dict[str, Any]:
    """Return auth-related kwargs based on settings.LLM_AUTH_METHOD."""
    method = settings.LLM_AUTH_METHOD
    if method == "header":
        if not settings.LLM_API_HEADER_VALUE:
            logger.warning("LLM_AUTH_METHOD=header but LLM_API_HEADER_VALUE is empty")
            return {}
        return {
            "extra_headers": {
                settings.LLM_API_HEADER_NAME: settings.LLM_API_HEADER_VALUE,
            }
        }
    if method == "key":
        return {"api_key": settings.LLM_API_KEY} if settings.LLM_API_KEY else {}
    logger.warning("Unknown LLM_AUTH_METHOD=%r, falling back to no-auth", method)
    return {}


def _base_kwargs(model: str) -> dict[str, Any]:
    """Build kwargs common to both ADK LiteLlm construction and direct
    litellm.completion calls."""
    kw: dict[str, Any] = {"model": model}
    if settings.LLM_API_BASE:
        kw["api_base"] = settings.LLM_API_BASE
    kw.update(_auth_kwargs())
    return kw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_adk_model(model: str | None = None) -> LiteLlm:
    """Build the ADK LiteLlm wrapper for the orchestrator (agent.py).

    Uses settings.LLM_MODEL by default.
    """
    return LiteLlm(**_base_kwargs(model or settings.LLM_MODEL))


def call_llm(
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    **extra: Any,
) -> str:
    """Direct LLM call for tool-level use (analyze.py, interpret.py).

    Returns the assistant text content, stripped.
    Raises exceptions from litellm for the caller to handle.
    """
    response = litellm.completion(
        **_base_kwargs(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **extra,
    )
    return response.choices[0].message.content.strip()
