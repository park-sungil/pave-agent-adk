"""LLM access. Flip settings.LLM_AUTH between 'key' and 'header'."""

import litellm
from google.adk.models.lite_llm import LiteLlm

from pave_agent import settings


# vLLM rejects assistant tool_call messages without `content` field.
# Monkey-patch litellm.completion / acompletion to inject content=None
# right before the HTTP call (CustomLogger callback runs too late /
# may receive a copy of messages instead of the original reference).

_original_completion = litellm.completion
_original_acompletion = litellm.acompletion


def _fix_messages(messages):
    if not messages:
        return
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("content") is None:
            msg["content"] = ""


def _patched_completion(*args, **kwargs):
    _fix_messages(kwargs.get("messages"))
    return _original_completion(*args, **kwargs)


async def _patched_acompletion(*args, **kwargs):
    _fix_messages(kwargs.get("messages"))
    return await _original_acompletion(*args, **kwargs)


litellm.completion = _patched_completion
litellm.acompletion = _patched_acompletion


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
