from pathlib import Path
from typing import Any

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.bootstrap.tools import create_tool_executor
from sentinel.llm.base import LLMProvider
from sentinel.workflows.sentinel_graph import create_sentinel_graph


def create_sentinel_application(
        *,
        llm_provider: LLMProvider,
        repository_root: Path,
) -> Any:
    """Create the complete Sentinel application."""

    tool_executor = create_tool_executor(
        repository_root=repository_root,
    )

    planner_agent = PlannerAgent(
        llm_provider=llm_provider,
    )

    investigator_agent = InvestigatorAgent(
        tool_executor=tool_executor,
    )

    return create_sentinel_graph(
        planner_agent,
        investigator_agent,
    )