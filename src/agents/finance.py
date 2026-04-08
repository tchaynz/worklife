"""Finance Analyst — live crypto/stock prices, portfolio awareness."""
from __future__ import annotations

import json

from src.agents.base import AgentResponse, BaseAgent, registry
from src.memory.context import format_memories_for_prompt
from src.tools.crypto import COIN_IDS, get_crypto_prices
from src.tools.stocks import POSITIONS, get_all_stock_quotes
from src.utils.anthropic_client import client as anthropic_client
from src.utils.logger import log

_SYSTEM_PROMPT_TEMPLATE = """\
You are the Finance Analyst for Ted's WorkLife system.

## Your Domain
Crypto markets, stock positions, portfolio monitoring. You track prices, surface notable moves, and give Ted the information he needs to make his own decisions.

## What You Know About Ted
{memories}

## Your Tools
You have access to live price data for Ted's positions. When asked about prices or performance, ALWAYS call get_prices to fetch real-time data before answering.

## How You Respond
- Lead with the key number or signal
- Include 24h % change for each position
- Flag any position >5% move with "ALERT:"
- Keep it under 150 words unless Ted asks for more detail
- Use plain language, no markdown formatting
- No trade recommendations — information only
"""

_TOOLS = [
    {
        "name": "get_prices",
        "description": "Fetch current USD prices and 24h % change for Ted's crypto and/or stock positions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_crypto": {
                    "type": "boolean",
                    "description": "Include XRP, XLM, FET, LINK, SOL prices.",
                    "default": True,
                },
                "include_stocks": {
                    "type": "boolean",
                    "description": "Include SMCI stock price.",
                    "default": True,
                },
            },
        },
    }
]


async def _fetch_prices(include_crypto: bool = True, include_stocks: bool = True) -> str:
    """Execute the get_prices tool and return JSON string."""
    import asyncio
    results: dict = {}

    tasks = []
    if include_crypto:
        tasks.append(get_crypto_prices())
    if include_stocks:
        tasks.append(get_all_stock_quotes())

    fetched = await asyncio.gather(*tasks)
    idx = 0
    if include_crypto:
        results["crypto"] = fetched[idx]
        idx += 1
    if include_stocks:
        results["stocks"] = fetched[idx]

    return json.dumps(results)


class FinanceAgent(BaseAgent):
    name = "finance"

    async def process(self, message: str, context: dict) -> AgentResponse:
        memories = format_memories_for_prompt(context.get("memories", []))
        system = _SYSTEM_PROMPT_TEMPLATE.format(memories=memories)

        # Build conversation history for this turn
        history = _build_history(context.get("messages", []), message)

        log.info("finance_agent_start", message_length=len(message))

        # Agentic loop: let Claude call get_prices if it needs to
        response_text = await _run_agent_loop(system, history)

        return AgentResponse(content=response_text, agent_name=self.name)


async def _run_agent_loop(system: str, messages: list[dict]) -> str:
    """Run the tool-use agentic loop until Claude returns a final text response."""
    current_messages = list(messages)

    for _ in range(3):  # max 3 tool calls before giving up
        response = await anthropic_client.complete_with_tools(
            system=system,
            messages=current_messages,
            tools=_TOOLS,
            agent_name="finance",
        )

        # Plain text response — we're done
        if response["stop_reason"] == "end_turn":
            return response["text"]

        # Tool call requested
        if response["stop_reason"] == "tool_use":
            tool_calls = response["tool_calls"]
            # Append assistant message with tool_use blocks
            current_messages.append({
                "role": "assistant",
                "content": response["raw_content"],
            })

            # Execute each tool and collect results
            tool_results = []
            for call in tool_calls:
                if call["name"] == "get_prices":
                    inputs = call["input"]
                    price_data = await _fetch_prices(
                        include_crypto=inputs.get("include_crypto", True),
                        include_stocks=inputs.get("include_stocks", True),
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": price_data,
                    })
                    log.info("finance_tool_executed", tool="get_prices")

            # Only append the user message if there are actual tool results;
            # an empty content list would cause a 400 from the Anthropic API.
            if tool_results:
                current_messages.append({"role": "user", "content": tool_results})
            continue

        break  # unexpected stop reason

    return "I'm having trouble fetching your portfolio data right now. Try again in a moment."


def _build_history(stored_messages: list[dict], new_message: str) -> list[dict]:
    """Convert stored DB messages into the Anthropic messages format."""
    history = []
    for m in stored_messages:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant"):
            history.append({"role": role, "content": content})

    history.append({"role": "user", "content": new_message})
    return history


# Register on import
registry.register(FinanceAgent())
