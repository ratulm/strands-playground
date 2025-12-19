"""Agent components for the evolution system."""

from .researcher_agent import create_researcher_agent, RESEARCHER_SYSTEM_PROMPT
from .supervisor_agent import create_supervisor_agent, SUPERVISOR_SYSTEM_PROMPT

__all__ = [
    "create_researcher_agent",
    "RESEARCHER_SYSTEM_PROMPT",
    "create_supervisor_agent",
    "SUPERVISOR_SYSTEM_PROMPT",
]
