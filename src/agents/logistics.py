"""Logistics Manager — schedule awareness via Google Calendar."""
from __future__ import annotations

import json

from src.agents.base import AgentResponse, BaseAgent, registry
from src.memory.context import format_memories_for_prompt
from src.tools.calendar import (
    format_events_for_prompt,
    get_todays_events,
    get_tomorrows_events,
    get_weeks_events,
)
from src.utils.anthropic_client import client as anthropic_client
from src.utils.logger import log

_SYSTEM_PROMPT_TEMPLATE = """\
You are the Logistics Manager for Ted's WorkLife system.

## Your Domain
Schedule, calendar, time management, and day-to-day logistics. You help Ted understand his upcoming commitments and surface conflicts or important gaps.

## What You Know About Ted
{memories}

## Your Tools
You have access to Ted's Google Calendar. When asked about schedule, meetings, or time, ALWAYS call get_schedule to fetch live calendar data before answering.

## How You Respond
- Lead with the most important thing (first meeting, busiest day, conflict)
- List events chronologically with times in ET
- Flag back-to-back meetings or days with no free time
- Keep it under 200 words unless Ted asks for more
- Use plain language, no markdown formatting
"""

_TOOLS = [
    {
        "name": "get_schedule",
        "description": "Fetch Ted's Google Calendar events for a given time scope.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "week"],
                    "description": "Which time window to fetch. Default: 'today'.",
                    "default": "today",
                }
            },
        },
    }
]


async def _fetch_schedule(scope: str) -> str:
    """Execute the get_schedule tool and return JSON string."""
    if scope == "tomorrow":
        events = await get_tomorrows_events()
    elif scope == "week":
        events = await get_weeks_events()
    else:
        events = await get_todays_events()

    return json.dumps({"scope": scope, "events": events})


class LogisticsAgent(BaseAgent):
    name = "logistics"

    async def process(self, message: str, context: dict) -> AgentResponse:
        memories = format_memories_for_prompt(context.get("memories", []))
        system = _SYSTEM_PROMPT_TEMPLATE.format(memories=memories)
        history = _build_history(context.get("messages", []), message)

        log.info("logistics_agent_start", message_length=len(message))

        response_text = await _run_agent_loop(system, history)
        return AgentResponse(content=response_text, agent_name=self.name)


async def _run_agent_loop(system: str, messages: list[dict]) -> str:
    """Run the tool-use agentic loop until Claude returns a final text response."""
    current_messages = list(messages)

    for _ in range(3):
        response = await anthropic_client.complete_with_tools(
            system=system,
            messages=current_messages,
            tools=_TOOLS,
            agent_name="logistics",
        )

        if response["stop_reason"] == "end_turn":
            return response["text"]

        if response["stop_reason"] == "tool_use":
            current_messages.append({
                "role": "assistant",
                "content": response["raw_content"],
            })

            tool_results = []
            for call in response["tool_calls"]:
                if call["name"] == "get_schedule":
                    scope = call["input"].get("scope", "today")
                    schedule_data = await _fetch_schedule(scope)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": schedule_data,
                    })
                    log.info("logistics_tool_executed", tool="get_schedule", scope=scope)

            current_messages.append({"role": "user", "content": tool_results})
            continue

        break

    return "I'm having trouble accessing your calendar right now. Try again in a moment."


def _build_history(stored_messages: list[dict], new_message: str) -> list[dict]:
    history = []
    for m in stored_messages:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant"):
            history.append({"role": role, "content": content})
    history.append({"role": "user", "content": new_message})
    return history


# Register on import
registry.register(LogisticsAgent())
