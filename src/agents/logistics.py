"""Logistics Manager — schedule awareness via Google Calendar."""
from __future__ import annotations

import json

from src.agents.base import AgentResponse, BaseAgent, build_message_history, registry
from src.memory.context import format_memories_for_prompt
from src.tools.calendar import (
    get_todays_events,
    get_tomorrows_events,
    get_weeks_events,
)
from src.tools.gmail import create_draft, get_thread, get_unread_emails, search_emails, send_email
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
- search_emails: search any emails (read or unread) using Gmail query syntax
- get_thread: fetch the full thread for a specific email
- create_draft: compose a draft email for Ted to review before sending
- send_email: send an email immediately on Ted's behalf

When asked about schedule or calendar, call get_schedule first.
When asked about unread/new emails, call get_emails first.
When asked about a specific or past email, call search_emails.
When Ted asks you to write or draft an email, use create_draft — always confirm recipient, subject, and body with him first unless all three are clearly stated.
When Ted explicitly says to send (not just draft), use send_email.

Gmail query syntax examples: "from:boss@example.com", "subject:invoice", "after:2026/04/01".

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
        "name": "search_emails",
        "description": "Search Ted's Gmail using a query string. Use this to find read or unread emails by sender, subject, date, or any other criteria. Supports Gmail search syntax: 'from:someone@example.com', 'subject:invoice', 'after:2026/04/01', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query. Examples: 'from:boss@co.com', 'subject:receipt after:2026/04/01', 'from:amazon'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return. Default: 10.",
                    "default": 10,
                },
            },
            "required": ["query"],
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
    {
        "name": "create_draft",
        "description": "Create a draft email in Ted's Gmail for him to review and send later. Use this unless Ted explicitly asks to send immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Plain text email body."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email immediately from Ted's Gmail. Only use this when Ted explicitly says to send — otherwise use create_draft.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Plain text email body."},
            },
            "required": ["to", "subject", "body"],
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


async def _search_emails(query: str, max_results: int = 10) -> str:
    emails = await search_emails(query=query, max_results=max_results)
    return json.dumps({"query": query, "emails": emails})


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
                elif call["name"] == "search_emails":
                    query = call["input"].get("query", "in:inbox")
                    max_results = call["input"].get("max_results", 10)
                    result = await _search_emails(query, max_results)
                    log.info("logistics_tool_executed", tool="search_emails", query=query)
                elif call["name"] == "get_thread":
                    thread_id = call["input"].get("thread_id", "")
                    result = await _fetch_thread(thread_id)
                    log.info("logistics_tool_executed", tool="get_thread", thread_id=thread_id)
                elif call["name"] == "create_draft":
                    inp = call["input"]
                    outcome = await create_draft(inp["to"], inp["subject"], inp["body"])
                    result = json.dumps(outcome)
                    log.info("logistics_tool_executed", tool="create_draft", to=inp.get("to"))
                elif call["name"] == "send_email":
                    inp = call["input"]
                    outcome = await send_email(inp["to"], inp["subject"], inp["body"])
                    result = json.dumps(outcome)
                    log.info("logistics_tool_executed", tool="send_email", to=inp.get("to"))
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
    return build_message_history(stored_messages, new_message)


# Register on import
registry.register(LogisticsAgent())
