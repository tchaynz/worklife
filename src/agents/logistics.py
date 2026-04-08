"""Logistics Manager — schedule awareness via Google Calendar."""
from __future__ import annotations

import json

from src.agents.base import AgentResponse, BaseAgent, registry
from src.memory.context import format_memories_for_prompt
from src.tools.calendar import (
    get_todays_events,
    get_tomorrows_events,
    get_weeks_events,
)
from src.tools.gmail import get_thread, get_unread_emails
from src.utils.anthropic_client import client as anthropic_client
from src.utils.logger import log

_SYSTEM_PROMPT_TEMPLATE = """\
You are the Logistics Manager for Ted's WorkLife system.

## Your Domain
Schedule, calendar, email, and day-to-day logistics. You help Ted understand his upcoming commitments, surface important emails, and keep him on top of his day.

## What You Know About Ted
{memories}

## Your Tools
- get_schedule: fetch Ted's Google Calendar events
- get_emails: fetch Ted's recent unread emails
- get_thread: fetch all messages in a specific email thread

When asked about schedule or calendar, call get_schedule first.
When asked about email, call get_emails first.
Always fetch live data before answering — never guess.

## How You Respond
- Lead with the most important thing
- For calendar: list events chronologically with times in ET
- For email: lead with sender and subject, one line per email
- Flag anything urgent or time-sensitive
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
    },
    {
        "name": "get_emails",
        "description": "Fetch Ted's recent unread emails from Gmail inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Number of emails to fetch. Default: 10.",
                    "default": 10,
                }
            },
        },
    },
    {
        "name": "get_thread",
        "description": "Fetch the full message thread for a specific email thread ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "The Gmail thread ID to fetch.",
                }
            },
            "required": ["thread_id"],
        },
    },
]


async def _fetch_schedule(scope: str) -> str:
    if scope == "tomorrow":
        events = await get_tomorrows_events()
    elif scope == "week":
        events = await get_weeks_events()
    else:
        events = await get_todays_events()
    return json.dumps({"scope": scope, "events": events})


async def _fetch_emails(max_results: int = 10) -> str:
    emails = await get_unread_emails(max_results=max_results)
    return json.dumps({"emails": emails})


async def _fetch_thread(thread_id: str) -> str:
    messages = await get_thread(thread_id)
    return json.dumps({"thread_id": thread_id, "messages": messages})


class LogisticsAgent(BaseAgent):
    name = "logistics"

    async def process(self, message: str, context: dict) -> AgentResponse:
        memories = format_memories_for_prompt(context.get("memories", []))
        system = _SYSTEM_PROMPT_TEMPLATE.format(memories=memories)
        history = _build_history(context.get("messages", []), message)

        log.info("logistics_agent_start", message_length=len(message))

        response_text = await _run_agent_loop(system, history)
        return AgentResponse(content=response_text, agent_name=self.name)


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """Validate and sanitize messages before sending to the Anthropic API.

    Removes any messages with empty or None content to prevent 400 errors.
    """
    sanitized = []
    for msg in messages:
        content = msg.get("content")
        # Drop messages with None or empty-string content
        if content is None:
            log.warning("logistics_dropping_message_no_content", role=msg.get("role"))
            continue
        if isinstance(content, str) and not content.strip():
            log.warning("logistics_dropping_empty_message", role=msg.get("role"))
            continue
        if isinstance(content, list) and not content:
            log.warning("logistics_dropping_empty_list_message", role=msg.get("role"))
            continue
        sanitized.append(msg)
    return sanitized


async def _run_agent_loop(system: str, messages: list[dict]) -> str:
    """Run the tool-use agentic loop until Claude returns a final text response."""
    current_messages = list(messages)

    for _ in range(3):
        response = await anthropic_client.complete_with_tools(
            system=system,
            messages=_sanitize_messages(current_messages),
            tools=_TOOLS,
            agent_name="logistics",
        )

        if response["stop_reason"] == "end_turn":
            return response["text"]

        if response["stop_reason"] == "tool_use":
            # Ensure raw_content is a non-empty list of dicts before appending
            raw_content = response["raw_content"]
            if not isinstance(raw_content, list) or not raw_content:
                log.warning("logistics_invalid_raw_content", raw_content=raw_content)
                break
            current_messages.append({
                "role": "assistant",
                "content": raw_content,
            })

            tool_results = []
            for call in response["tool_calls"]:
                if call["name"] == "get_schedule":
                    scope = call["input"].get("scope", "today")
                    result = await _fetch_schedule(scope)
                    log.info("logistics_tool_executed", tool="get_schedule", scope=scope)
                elif call["name"] == "get_emails":
                    max_results = call["input"].get("max_results", 10)
                    result = await _fetch_emails(max_results)
                    log.info("logistics_tool_executed", tool="get_emails")
                elif call["name"] == "get_thread":
                    thread_id = call["input"].get("thread_id", "")
                    result = await _fetch_thread(thread_id)
                    log.info("logistics_tool_executed", tool="get_thread", thread_id=thread_id)
                else:
                    result = json.dumps({"error": f"unknown tool: {call['name']}"})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": result,
                })

            # Only append the user message if there are actual tool results;
            # an empty content list would cause a 400 from the Anthropic API.
            if tool_results:
                current_messages.append({"role": "user", "content": tool_results})
            continue

        break

    return "I'm having trouble accessing your calendar right now. Try again in a moment."


def _build_history(stored_messages: list[dict], new_message: str) -> list[dict]:
    """Convert stored DB messages into the Anthropic messages format.

    Handles content that was stored as a JSON string (e.g. assistant messages
    with tool_use blocks) by parsing it back into the original list structure.
    Filters out any messages with empty or None content.
    """
    history = []
    for m in stored_messages:
        role = m.get("role")
        content = m.get("content", "")
        if role not in ("user", "assistant"):
            continue

        # Content may have been serialised as a JSON string when stored in the
        # database (e.g. a list of tool_use blocks). Parse it back if so.
        if isinstance(content, str) and content.startswith(("[", "{")):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass  # Not valid JSON — treat as a plain string

        # Skip messages with empty or None content
        if content is None:
            continue
        if isinstance(content, str) and not content.strip():
            continue
        if isinstance(content, list) and not content:
            continue

        history.append({"role": role, "content": content})

    history.append({"role": "user", "content": new_message})
    return history


# Register on import
registry.register(LogisticsAgent())
