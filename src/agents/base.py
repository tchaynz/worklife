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


def build_message_history(stored_messages: list[dict], new_message: str) -> list[dict]:
    """Convert stored DB messages into Anthropic API format.

    - JSON-parses content strings that represent serialized tool_use blocks
    - Filters out empty-content messages
    - Merges consecutive same-role messages to satisfy the alternating-role requirement
    """
    import json

    history: list[dict] = []
    for m in stored_messages:
        role = m.get("role")
        content = m.get("content", "")
        if role not in ("user", "assistant"):
            continue

        # Content stored as a JSON string may be a list of tool_use blocks —
        # parse it back so the SDK receives the correct structure.
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, (list, dict)):
                    content = parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # Filter empty content
        if content is None:
            continue
        if isinstance(content, str) and not content.strip():
            continue
        if isinstance(content, list) and not content:
            continue

        # Merge consecutive same-role messages (only possible for plain text)
        if history and history[-1]["role"] == role and isinstance(content, str) and isinstance(history[-1]["content"], str):
            history[-1]["content"] += "\n" + content.strip()
        else:
            history.append({"role": role, "content": content})

    # Append the new user message
    new_content = new_message.strip()
    if history and history[-1]["role"] == "user" and isinstance(history[-1]["content"], str):
        history[-1]["content"] += "\n" + new_content
    else:
        history.append({"role": "user", "content": new_content})

    return history
