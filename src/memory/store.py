"""Supabase read/write for conversations, messages, and agent memory."""
from __future__ import annotations

import asyncio
from typing import Optional

from supabase import Client, create_client

from src.config import settings
from src.utils.logger import log

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


async def _run(fn, *args, **kwargs):
    """Run a synchronous Supabase call in a thread pool."""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

async def get_or_create_conversation(from_number: str) -> str:
    """Return the active conversation_id for a phone number, creating one if needed."""
    db = _get_client()

    def _query():
        return (
            db.table("conversations")
            .select("id")
            .order("last_message_at", desc=True)
            .limit(1)
            .execute()
        )

    result = await _run(_query)

    if result.data:
        conversation_id = result.data[0]["id"]
        log.debug("conversation_found", conversation_id=conversation_id)
        return conversation_id

    def _insert():
        return db.table("conversations").insert({"metadata": {"from_number": from_number}}).execute()

    created = await _run(_insert)
    conversation_id = created.data[0]["id"]
    log.info("conversation_created", conversation_id=conversation_id)
    return conversation_id


async def touch_conversation(conversation_id: str) -> None:
    """Update last_message_at timestamp."""
    db = _get_client()

    def _update():
        from datetime import datetime, timezone
        return (
            db.table("conversations")
            .update({"last_message_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", conversation_id)
            .execute()
        )

    await _run(_update)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
) -> None:
    """Persist a message to the messages table."""
    db = _get_client()

    def _insert():
        return db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "agent_name": agent_name,
        }).execute()

    await _run(_insert)
    await touch_conversation(conversation_id)
    log.debug("message_saved", role=role, agent_name=agent_name)


async def get_recent_messages(conversation_id: str, limit: int = 20) -> list[dict]:
    """Retrieve the most recent messages for a conversation, oldest first."""
    db = _get_client()

    def _query():
        return (
            db.table("messages")
            .select("role, content, agent_name, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    result = await _run(_query)
    messages = list(reversed(result.data or []))
    log.debug("messages_fetched", count=len(messages))
    return messages


# ---------------------------------------------------------------------------
# Agent memory
# ---------------------------------------------------------------------------

async def get_agent_memories(agent_name: str, category: Optional[str] = None) -> list[dict]:
    """Retrieve long-term memories for an agent, optionally filtered by category."""
    db = _get_client()

    def _query():
        q = (
            db.table("agent_memory")
            .select("category, content, metadata")
            .eq("agent_name", agent_name)
            .is_("expires_at", "null")  # exclude expired
            .order("created_at", desc=False)
        )
        if category:
            q = q.eq("category", category)
        return q.execute()

    result = await _run(_query)
    return result.data or []


async def save_memory(
    agent_name: str,
    category: str,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    """Persist a memory entry (no embedding — text-based retrieval only for now)."""
    db = _get_client()

    def _insert():
        return db.table("agent_memory").insert({
            "agent_name": agent_name,
            "category": category,
            "content": content,
            "metadata": metadata or {},
        }).execute()

    await _run(_insert)
    log.debug("memory_saved", agent_name=agent_name, category=category)
