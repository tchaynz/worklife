"""MCP server — exposes WorkLife's Chief of Staff to claude.ai."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import settings
from src.memory.store import get_or_create_conversation, save_message
from src.utils.logger import log

# Stable identifier so claude.ai gets its own persistent conversation thread,
# separate from the WhatsApp thread.
_CLAUDE_AI_USER = "claude_ai"

mcp = FastMCP("WorkLife")


@mcp.tool()
async def ask_worklife(message: str) -> str:
    """Send a message to your WorkLife Chief of Staff and get a response."""
    # Import here to avoid circular imports at module load time
    from src.agents.chief_of_staff import chief_of_staff

    conversation_id = await get_or_create_conversation(_CLAUDE_AI_USER)
    await save_message(conversation_id, "user", message)

    reply = await chief_of_staff.handle(message, conversation_id)

    await save_message(conversation_id, "assistant", reply)
    log.info("mcp_request_handled", message_length=len(message), reply_length=len(reply))
    return reply


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry the correct Bearer token."""

    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request, call_next):
        if self._api_key:
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != self._api_key:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


def get_mcp_asgi_app():
    """Return the MCP server wrapped with Bearer auth, ready to mount in FastAPI."""
    inner = mcp.streamable_http_app()
    return _BearerAuthMiddleware(inner, api_key=settings.mcp_api_key)
