"""Build the context dict passed to every agent: recent messages + relevant memories."""
from __future__ import annotations

from src.memory.store import get_agent_memories, get_recent_messages


async def build_context(conversation_id: str, agent_name: str) -> dict:
    """Return context for an agent: recent conversation history + its long-term memories.

    Args:
        conversation_id: Active conversation UUID.
        agent_name: The specialist (or 'chief_of_staff') receiving the context.

    Returns:
        {
            "messages": [{"role": ..., "content": ..., "agent_name": ...}, ...],
            "memories": [{"category": ..., "content": ...}, ...],
        }
    """
    messages, memories = await _gather(conversation_id, agent_name)
    return {"messages": messages, "memories": memories}


async def _gather(conversation_id: str, agent_name: str):
    import asyncio
    return await asyncio.gather(
        get_recent_messages(conversation_id),
        get_agent_memories(agent_name),
    )


def format_memories_for_prompt(memories: list[dict]) -> str:
    """Render memories as a bullet list for inclusion in a system prompt."""
    if not memories:
        return "(no stored context)"
    lines = []
    for m in memories:
        category = m.get("category", "fact")
        content = m.get("content", "")
        lines.append(f"[{category}] {content}")
    return "\n".join(lines)
