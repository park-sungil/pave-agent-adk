"""LLM access. Flip settings.LLM_AUTH_METHOD to switch between `key` and `header`."""

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


def build_adk_model(model=None):
    model = model or settings.LLM_MODEL
    if settings.LLM_AUTH_METHOD == "header":
        return LiteLlm(
            model=model,
            api_base=settings.LLM_API_BASE_HEADER,
            extra_headers={settings.LLM_API_HEADER_NAME: settings.LLM_API_HEADER_VALUE},
        )
    return LiteLlm(
        model=model,
        api_base=settings.LLM_API_BASE_KEY,
        api_key=settings.LLM_API_KEY,
    )


def call_llm(model, messages, temperature=0.0, max_tokens=4096, **extra):
    response = litellm.completion(
        messages=messages, temperature=temperature, max_tokens=max_tokens,
        **build_adk_model(model)._additional_args, **extra,
    )
    return response.choices[0].message.content.strip()
