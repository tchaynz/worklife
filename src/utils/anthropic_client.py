import time

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.utils.logger import log

MODEL = "claude-sonnet-4-20250514"

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


class AnthropicClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        agent_name: str = "unknown",
        max_tokens: int = 1024,
    ) -> str:
        """Send a message to Claude and return the text response.

        Args:
            system: System prompt for the agent.
            messages: Conversation history as [{"role": "user"|"assistant", "content": "..."}].
            agent_name: Name of the calling agent (for logging).
            max_tokens: Maximum tokens in the response.

        Returns:
            The text content of Claude's response.

        Raises:
            anthropic.APIError: On non-retryable API errors or after retries exhausted.
        """
        start = time.monotonic()

        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "anthropic_complete",
            agent_name=agent_name,
            model=MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        return response.content[0].text

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        agent_name: str = "unknown",
        max_tokens: int = 1024,
    ) -> dict:
        """Send a message with tool definitions and return structured response.

        Returns:
            {
                "stop_reason": "end_turn" | "tool_use",
                "text": str,               # final text (when stop_reason == "end_turn")
                "tool_calls": [...],       # (when stop_reason == "tool_use")
                "raw_content": [...],      # raw content blocks for re-appending to history
            }
        """
        start = time.monotonic()

        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "anthropic_complete_with_tools",
            agent_name=agent_name,
            model=MODEL,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        text = ""
        tool_calls = []
        raw_content = []

        for block in response.content:
            raw_content.append(block)
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return {
            "stop_reason": response.stop_reason,
            "text": text,
            "tool_calls": tool_calls,
            "raw_content": raw_content,
        }


# Module-level singleton — import and use directly
client = AnthropicClient()
