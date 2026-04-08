"""PAVE agent: Semiconductor PPA analysis.

ADK entry point. Run with: adk web .
"""

import logging

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from pave_agent import llm, settings
from pave_agent.prompts import INSTRUCTION
from pave_agent.tools.query_data import query_versions, query_ppa
from pave_agent.tools.analyze import analyze
from pave_agent.tools.interpret import interpret

_log = logging.getLogger("pave_agent")
_log.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    _log.addHandler(_h)


def _init_state(callback_context: CallbackContext) -> None:
    """Pre-load PDK versions and default WNS config into session state on first run."""
    if "_versions_loaded" not in callback_context.state:
        from pave_agent.tools.query_data import load_default_wns_config, load_versions
        load_versions(callback_context.state)
        load_default_wns_config(callback_context.state)
        callback_context.state["_versions_loaded"] = True


root_agent = Agent(
    name="pave_agent",
    model=llm.build_adk_model(),
    description="반도체 PDK Cell-level PPA 분석 챗봇 에이전트",
    instruction=INSTRUCTION,
    tools=[query_versions, query_ppa, analyze, interpret],
    before_agent_callback=_init_state,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    ),
)
