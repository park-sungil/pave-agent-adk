"""LLM access. Flip settings.LLM_AUTH between 'key' and 'header'."""

import litellm
from google.adk.models.lite_llm import LiteLlm
from litellm.integrations.custom_logger import CustomLogger

from pave_agent import settings


class _FixAssistantContent(CustomLogger):
    """vLLM rejects assistant tool_call messages without `content` field."""

    def log_pre_api_call(self, model, messages, kwargs):
        for msg in messages:
            if msg.get("role") == "assistant" and "content" not in msg:
                msg["content"] = None


litellm.callbacks.append(_FixAssistantContent())


# ---------------------------------------------------------------------------
# key mode: api_base + api_key. Per-component model override possible.
# ---------------------------------------------------------------------------

_KEY_AUTH = {
    "api_base": settings.LLM_API_BASE or None,
    "api_key": settings.LLM_API_KEY or None,
}


def build_adk_model_key():
    return LiteLlm(model=settings.LLM_MODEL, **_KEY_AUTH)


def call_llm_key(model, messages, temperature=0.0, max_tokens=4096):
    response = litellm.completion(
        model=model,
        **_KEY_AUTH,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# header mode: api_base + extra_headers. Single model only.
# ---------------------------------------------------------------------------

_HEADER_AUTH = {
    "model": settings.LLM_MODEL,
    "api_base": settings.LLM_API_BASE_HEADER,
    "extra_headers": {
        "x-dep-ticket": settings.VLLM_DEP_TICKET,
        "Send-System-Name": settings.VLLM_SEND_SYSTEM_NAME,
        "User-Id": settings.VLLM_USER_ID,
        "User-Type": settings.VLLM_USER_TYPE,
    },
}


def build_adk_model_header():
    return LiteLlm(**_HEADER_AUTH)


def call_llm_header(messages, temperature=0.0, max_tokens=4096):
    response = litellm.completion(
        **_HEADER_AUTH,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Dispatchers
# ---------------------------------------------------------------------------

def build_adk_model():
    if settings.LLM_AUTH == "header":
        return build_adk_model_header()
    return build_adk_model_key()


def call_llm(model, messages, temperature=0.0, max_tokens=4096):
    if settings.LLM_AUTH == "header":
        return call_llm_header(messages, temperature, max_tokens)
    return call_llm_key(model, messages, temperature, max_tokens)
