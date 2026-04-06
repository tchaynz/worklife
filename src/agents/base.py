"""Base agent interface and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    content: str
    agent_name: str


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def process(self, message: str, context: dict) -> AgentResponse:
        ...


# ---------------------------------------------------------------------------
# Agent registry — CoS looks up available specialists here
# ---------------------------------------------------------------------------

class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    @property
    def available(self) -> list[str]:
        return list(self._agents.keys())


registry = AgentRegistry()
