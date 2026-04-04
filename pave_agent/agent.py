"""PAVE agent: Semiconductor PPA analysis.

ADK entry point. Run with: adk web .
"""

import logging

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm

from pave_agent import settings
from pave_agent.prompts import INSTRUCTION

_log = logging.getLogger("pave_agent")
_log.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    _log.addHandler(_h)
from pave_agent.tools.query_data import query_data
from pave_agent.tools.analyze import analyze
from pave_agent.tools.interpret import interpret


def _init_state(callback_context: CallbackContext) -> None:
    """Pre-load all PDK versions into session state on first run."""
    if "_versions_loaded" not in callback_context.state:
        from pave_agent.tools.query_data import load_versions
        load_versions(callback_context.state)
        callback_context.state["_versions_loaded"] = True


_llm = LiteLlm(
    model=settings.LLM_MODEL,
    api_base=settings.LLM_API_BASE or None,
    api_key=settings.LLM_API_KEY or None,
)

root_agent = Agent(
    name="pave_agent",
    model=_llm,
    description="반도체 PDK Cell-level PPA 분석 챗봇 에이전트",
    instruction=INSTRUCTION,
    tools=[query_data, analyze, interpret],
    before_agent_callback=_init_state,
)
