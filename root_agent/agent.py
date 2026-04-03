"""Root agent: platform-level entry point.

ADK discovers this directory. Routes to domain sub-agents.
Run with: adk web .
"""

from agents.pave_agent.agent import pave_agent

# For now, PAVE is the only domain — use it directly as root.
# When more domains are added, replace with:
#   root_agent = Agent(name="root", sub_agents=[pave_agent, x_agent, ...])
root_agent = pave_agent
