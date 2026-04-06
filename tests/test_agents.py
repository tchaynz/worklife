"""Tests for specialist agents (Finance and Logistics)."""
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.finance import FinanceAgent
from src.agents.logistics import LogisticsAgent
from src.tools.calendar import _format_event_for_prompt, _parse_event


# ---------------------------------------------------------------------------
# Calendar tool unit tests (pure, no I/O)
# ---------------------------------------------------------------------------

class TestParseEvent:
    def test_timed_event(self):
        raw = {
            "summary": "Design sync",
            "start": {"dateTime": "2026-04-06T14:00:00Z"},
            "end": {"dateTime": "2026-04-06T15:00:00Z"},
            "location": "Zoom",
            "attendees": [{"email": "alice@example.com"}, {"email": "me@example.com", "self": True}],
        }
        event = _parse_event(raw)
        assert event["summary"] == "Design sync"
        assert event["all_day"] is False
        assert event["location"] == "Zoom"
        assert "alice@example.com" in event["attendees"]
        assert "me@example.com" not in event["attendees"]  # self excluded

    def test_all_day_event(self):
        raw = {
            "summary": "Holiday",
            "start": {"date": "2026-04-07"},
            "end": {"date": "2026-04-08"},
        }
        event = _parse_event(raw)
        assert event["all_day"] is True
        assert event["summary"] == "Holiday"

    def test_missing_summary_uses_default(self):
        raw = {"start": {"date": "2026-04-07"}, "end": {"date": "2026-04-08"}}
        event = _parse_event(raw)
        assert event["summary"] == "(No title)"

    def test_description_truncated(self):
        raw = {
            "summary": "Test",
            "start": {"date": "2026-04-07"},
            "end": {"date": "2026-04-08"},
            "description": "x" * 300,
        }
        event = _parse_event(raw)
        assert len(event["description"]) == 200


class TestFormatEvent:
    def test_all_day_format(self):
        event = {
            "summary": "Holiday",
            "start": "2026-04-07",
            "all_day": True,
            "location": "",
            "attendees": [],
        }
        line = _format_event_for_prompt(event)
        assert "All day" in line
        assert "Holiday" in line

    def test_timed_event_includes_location(self):
        event = {
            "summary": "Standup",
            "start": "2026-04-06T13:00:00+00:00",
            "all_day": False,
            "location": "Slack",
            "attendees": [],
        }
        line = _format_event_for_prompt(event)
        assert "Standup" in line
        assert "Slack" in line


# ---------------------------------------------------------------------------
# Logistics agent routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logistics_agent_calls_calendar_tool():
    agent = LogisticsAgent()
    context = {"messages": [], "memories": []}

    tool_response = {
        "stop_reason": "tool_use",
        "text": "",
        "tool_calls": [{"id": "t1", "name": "get_schedule", "input": {"scope": "today"}}],
        "raw_content": [],
    }
    final_response = {
        "stop_reason": "end_turn",
        "text": "You have 3 meetings today.",
        "tool_calls": [],
        "raw_content": [],
    }

    with patch("src.agents.logistics.anthropic_client") as mock_client, \
         patch("src.agents.logistics._fetch_schedule", new=AsyncMock(return_value='{"scope":"today","events":[]}')):
        mock_client.complete_with_tools = AsyncMock(side_effect=[tool_response, final_response])
        result = await agent.process("What's my day look like?", context)

    assert result.content == "You have 3 meetings today."
    assert result.agent_name == "logistics"


# ---------------------------------------------------------------------------
# Finance agent tool-use loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finance_agent_calls_prices_tool():
    agent = FinanceAgent()
    context = {"messages": [], "memories": []}

    tool_response = {
        "stop_reason": "tool_use",
        "text": "",
        "tool_calls": [{"id": "t1", "name": "get_prices", "input": {"include_crypto": True, "include_stocks": True}}],
        "raw_content": [],
    }
    final_response = {
        "stop_reason": "end_turn",
        "text": "XRP is at $0.52, up 3.1% today.",
        "tool_calls": [],
        "raw_content": [],
    }

    with patch("src.agents.finance.anthropic_client") as mock_client, \
         patch("src.agents.finance._fetch_prices", new=AsyncMock(return_value='{"crypto":{},"stocks":{}}')):
        mock_client.complete_with_tools = AsyncMock(side_effect=[tool_response, final_response])
        result = await agent.process("How are my positions doing?", context)

    assert "XRP" in result.content
    assert result.agent_name == "finance"
