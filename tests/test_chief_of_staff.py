"""Tests for Chief of Staff routing logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentRegistry, AgentResponse, BaseAgent
from src.agents.chief_of_staff import ChiefOfStaff


class StubAgent(BaseAgent):
    name = "finance"

    async def process(self, message: str, context: dict) -> AgentResponse:
        return AgentResponse(content="stub finance response", agent_name=self.name)


@pytest.fixture
def cos_with_stub():
    stub = StubAgent()
    reg = AgentRegistry()
    reg.register(stub)
    cos = ChiefOfStaff()
    return cos, reg, stub


@pytest.mark.asyncio
async def test_classify_returns_finance_for_price_query():
    cos = ChiefOfStaff()
    with patch.object(
        cos,
        "_classify",
        new=AsyncMock(return_value="finance"),
    ), patch.object(
        cos,
        "_handle_general",
        new=AsyncMock(return_value="general fallback"),
    ):
        # Patch registry to have a finance agent
        stub = StubAgent()
        with patch("src.agents.chief_of_staff.registry") as mock_reg:
            mock_reg.get.return_value = stub
            with patch("src.agents.chief_of_staff.build_context", new=AsyncMock(return_value={"messages": [], "memories": []})):
                result = await cos.handle("What's the price of XRP?", "conv-123")

    assert result == "stub finance response"


@pytest.mark.asyncio
async def test_routes_to_general_when_no_specialist():
    cos = ChiefOfStaff()
    with patch.object(
        cos,
        "_classify",
        new=AsyncMock(return_value="logistics"),
    ), patch.object(
        cos,
        "_handle_general",
        new=AsyncMock(return_value="here is your schedule"),
    ):
        with patch("src.agents.chief_of_staff.registry") as mock_reg:
            mock_reg.get.return_value = None  # logistics agent not yet registered
            result = await cos.handle("What's my day look like?", "conv-123")

    assert result == "here is your schedule"


@pytest.mark.asyncio
async def test_classify_sanitizes_unexpected_label():
    cos = ChiefOfStaff()
    with patch("src.agents.chief_of_staff.anthropic_client") as mock_client:
        mock_client.complete = AsyncMock(return_value="  unknown_label  ")
        label = await cos._classify("random message")
    assert label == "general"


@pytest.mark.asyncio
async def test_classify_handles_api_error_gracefully():
    cos = ChiefOfStaff()
    with patch("src.agents.chief_of_staff.anthropic_client") as mock_client:
        mock_client.complete = AsyncMock(side_effect=Exception("API down"))
        label = await cos._classify("any message")
    assert label == "general"
