"""ADK entry point.

adk web . discovers this directory and loads root_agent.
Currently routes directly to the PAVE agent.
"""

from agents.pave.agent import pave_agent as root_agent

__all__ = ["root_agent"]
