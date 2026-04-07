"""LLM access. Auth switches on settings.LLM_AUTH_METHOD (`key` or `header`)."""

import litellm
from google.adk.models.lite_llm import LiteLlm
from litellm.integrations.custom_logger import CustomLogger

from pave_agent import settings


class _FixAssistantContent(CustomLogger):
    """vLLM rejects assistant messages without `content` key when tool_calls exist."""

    def log_pre_api_call(self, model, messages, kwargs):
        for msg in messages:
            if msg.get("role") == "assistant" and "content" not in msg:
                msg["content"] = None


if not any(type(cb).__name__ == "_FixAssistantContent" for cb in litellm.callbacks):
    litellm.callbacks.append(_FixAssistantContent())


def _kwargs(model):
    kw = {"model": model, "api_base": settings.LLM_API_BASE}
    if settings.LLM_AUTH_METHOD == "header":
        kw["extra_headers"] = {settings.LLM_API_HEADER_NAME: settings.LLM_API_HEADER_VALUE}
    else:
        kw["api_key"] = settings.LLM_API_KEY
    return kw


def build_adk_model(model=None):
    return LiteLlm(**_kwargs(model or settings.LLM_MODEL))


def call_llm(model, messages, temperature=0.0, max_tokens=4096, **extra):
    response = litellm.completion(**_kwargs(model), messages=messages,
                                  temperature=temperature, max_tokens=max_tokens, **extra)
    return response.choices[0].message.content.strip()
