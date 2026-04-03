"""PAVE agent: Semiconductor PPA analysis.

ADK entry point. Run with: adk web .
"""

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm

from pave_agent import settings
from pave_agent.prompts import INSTRUCTION
from pave_agent.tools.query_data import query_data
from pave_agent.tools.analyze import analyze
from pave_agent.tools.interpret import interpret


def _init_state(callback_context: CallbackContext) -> None:
    """Pre-load all PDK versions into session state on first run."""
    if "_versions_loaded" not in callback_context.state:
        from pave_agent.db import oracle_client
        from pave_agent.tools.query_data import _CACHE_TABLES

        for query_type, table in _CACHE_TABLES.items():
            cache_key = f"_cache_{table}"
            if cache_key not in callback_context.state:
                callback_context.state[cache_key] = oracle_client.execute_query(
                    f"SELECT * FROM {table}"
                )
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
