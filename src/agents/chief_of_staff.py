"""Chief of Staff — orchestrates specialist agents by classifying intent and routing."""
from __future__ import annotations

from src.agents.base import AgentResponse, BaseAgent, registry
from src.memory.context import build_context, format_memories_for_prompt
from src.utils.anthropic_client import client as anthropic_client
from src.utils.logger import log

_CLASSIFY_SYSTEM = """\
You are the routing layer for WorkLife, Ted's personal AI system.

Given a message, output ONLY one of these routing labels (no explanation):
  finance     — crypto prices, stock prices, portfolio, markets
  logistics   — calendar, schedule, tasks, reminders, travel logistics
  research    — research a topic, find information, news, analysis
  travel      — trip planning, flights, accommodation, destinations
  general     — everything else (chat, advice, questions that don't fit above)
"""

_GENERAL_SYSTEM_TEMPLATE = """\
You are WorkLife, Ted's personal AI Chief of Staff. You handle general questions and requests that don't fall into a specialist domain.

## What You Know About Ted
{memories}

## How You Respond
- Be direct and concise — this goes to WhatsApp, under 300 words
- Lead with the answer
- Use plain language, no markdown formatting
- No fluff
"""


class ChiefOfStaff:
    """Routes messages to specialist agents or handles directly."""

    async def handle(self, message: str, conversation_id: str) -> str:
        """Route a message and return the final reply text."""
        # Classify intent
        intent = await self._classify(message)
        log.info("cos_routing", intent=intent, message_length=len(message))

        # Try specialist agent
        agent = registry.get(intent)
        if agent is not None:
            context = await build_context(conversation_id, agent.name)
            response: AgentResponse = await agent.process(message, context)
            return response.content

        # No specialist registered yet — fall through to general response
        return await self._handle_general(message, conversation_id)

    async def _classify(self, message: str) -> str:
        """Ask Claude to classify the intent of the message."""
        try:
            label = await anthropic_client.complete(
                system=_CLASSIFY_SYSTEM,
                messages=[{"role": "user", "content": message}],
                agent_name="chief_of_staff_classifier",
                max_tokens=16,
            )
            label = label.strip().lower().split()[0]  # take first word only
            if label not in ("finance", "logistics", "research", "travel", "general"):
                label = "general"
        except Exception as exc:
            log.error("cos_classify_error", error=str(exc))
            label = "general"
        return label

    async def _handle_general(self, message: str, conversation_id: str) -> str:
        """Handle messages that don't map to a registered specialist."""
        from src.memory.store import get_agent_memories
        memories = await get_agent_memories("chief_of_staff")
        memory_text = format_memories_for_prompt(memories)
        system = _GENERAL_SYSTEM_TEMPLATE.format(memories=memory_text)

        try:
            return await anthropic_client.complete(
                system=system,
                messages=[{"role": "user", "content": message}],
                agent_name="chief_of_staff",
            )
        except Exception as exc:
            log.error("cos_general_error", error=str(exc))
            return "I'm having trouble right now. Please try again in a moment."


# Singleton used by the gateway
chief_of_staff = ChiefOfStaff()
