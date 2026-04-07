"""vLLM compatibility patch for LiteLLM.

Our internal vLLM server requires assistant messages to always include a
`content` field, even when tool_calls are present. LiteLLM's default
serialization omits `content` in that case, which causes a 422 error:

    {"loc":["body","messages",N,"content"],"msg":"Field required"}

Registering this callback on `litellm.callbacks` patches every outgoing
request in-place before it is sent, regardless of whether the caller is
the ADK `LiteLlm` wrapper (root agent) or a direct `litellm.completion`
call from a tool.

Importing this module registers the callback as a side effect.
"""

from __future__ import annotations

import litellm
from litellm.integrations.custom_logger import CustomLogger


class _FixAssistantContent(CustomLogger):
    def log_pre_api_call(self, model, messages, kwargs):  # noqa: D401
        for msg in messages:
            if msg.get("role") == "assistant" and "content" not in msg:
                msg["content"] = None


_instance = _FixAssistantContent()
if _instance not in litellm.callbacks:
    litellm.callbacks.append(_instance)
