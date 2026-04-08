"""Gmail API — read, compose, and send Ted's emails."""
from __future__ import annotations

import asyncio
import base64
import json
import re
from email.mime.text import MIMEText
from typing import Optional

from src.config import settings
from src.utils.logger import log

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
_USER_ID = "me"


def _build_service():
    """Build an authenticated Gmail service (sync)."""
    import google.oauth2.credentials
    import googleapiclient.discovery

    if not settings.google_token_json or not settings.google_credentials_json:
        raise RuntimeError("Google credentials not configured.")

    token_data = json.loads(settings.google_token_json)
    creds_data = json.loads(settings.google_credentials_json)
    client_config = creds_data.get("installed") or creds_data.get("web") or creds_data

    creds = google.oauth2.credentials.Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id") or client_config.get("client_id"),
        client_secret=token_data.get("client_secret") or client_config.get("client_secret"),
        scopes=_SCOPES,
    )

    return googleapiclient.discovery.build(
        "gmail", "v1", credentials=creds, cache_discovery=False
    )


def _decode_body(data: str) -> str:
    """Decode base64url-encoded email body."""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from a message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return _decode_body(data)

    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text:
                return text

    return ""


def _parse_headers(headers: list[dict]) -> dict:
    """Extract useful headers into a flat dict."""
    result = {}
    for h in headers:
        name = h.get("name", "").lower()
        if name in ("from", "to", "subject", "date"):
            result[name] = h.get("value", "")
    return result


def _parse_message(msg: dict, include_body: bool = False) -> dict:
    """Normalize a Gmail API message into a clean dict."""
    payload = msg.get("payload", {})
    headers = _parse_headers(payload.get("headers", []))

    result = {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", "(No subject)"),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
    }

    if include_body:
        body = _extract_body(payload)
        # Strip excessive whitespace
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        result["body"] = body[:2000]  # cap at 2000 chars

    return result


def _fetch_emails_sync(query: str, max_results: int = 10) -> list[dict]:
    """Fetch inbox messages matching a Gmail query string (sync)."""
    service = _build_service()

    list_result = (
        service.users()
        .messages()
        .list(userId=_USER_ID, q=query, maxResults=max_results)
        .execute()
    )

    messages = list_result.get("messages", [])
    if not messages:
        return []

    parsed = []
    for m in messages:
        full = (
            service.users()
            .messages()
            .get(userId=_USER_ID, id=m["id"], format="full")
            .execute()
        )
        parsed.append(_parse_message(full, include_body=False))

    return parsed


def _fetch_thread_sync(thread_id: str) -> list[dict]:
    """Fetch all messages in a thread (sync)."""
    service = _build_service()

    thread = (
        service.users()
        .threads()
        .get(userId=_USER_ID, id=thread_id, format="full")
        .execute()
    )

    return [_parse_message(m, include_body=True) for m in thread.get("messages", [])]


async def get_unread_emails(max_results: int = 10) -> list[dict]:
    """Fetch recent unread inbox emails."""
    return await search_emails("is:unread in:inbox", max_results)


async def search_emails(query: str, max_results: int = 10) -> list[dict]:
    """Search emails using a Gmail query string (supports read and unread)."""
    emails = await asyncio.to_thread(_fetch_emails_sync, query, max_results)
    log.info("gmail_search_fetched", query=query, count=len(emails))
    return emails


async def get_thread(thread_id: str) -> list[dict]:
    """Fetch all messages in a Gmail thread."""
    messages = await asyncio.to_thread(_fetch_thread_sync, thread_id)
    log.info("gmail_thread_fetched", thread_id=thread_id, count=len(messages))
    return messages


def _build_mime_message(to: str, subject: str, body: str) -> dict:
    """Build a base64url-encoded MIME message ready for the Gmail API."""
    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def _create_draft_sync(to: str, subject: str, body: str) -> dict:
    service = _build_service()
    message = _build_mime_message(to, subject, body)
    draft = service.users().drafts().create(userId=_USER_ID, body={"message": message}).execute()
    return {"draft_id": draft["id"], "to": to, "subject": subject}


def _send_email_sync(to: str, subject: str, body: str) -> dict:
    service = _build_service()
    message = _build_mime_message(to, subject, body)
    sent = service.users().messages().send(userId=_USER_ID, body=message).execute()
    return {"message_id": sent["id"], "to": to, "subject": subject}


async def create_draft(to: str, subject: str, body: str) -> dict:
    """Create a Gmail draft. Returns draft_id on success."""
    try:
        result = await asyncio.to_thread(_create_draft_sync, to, subject, body)
        log.info("gmail_draft_created", to=to, subject=subject)
        return result
    except Exception as exc:
        log.error("gmail_draft_error", to=to, subject=subject, error=str(exc))
        return {"error": str(exc)}


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email immediately. Returns message_id on success."""
    try:
        result = await asyncio.to_thread(_send_email_sync, to, subject, body)
        log.info("gmail_sent", to=to, subject=subject)
        return result
    except Exception as exc:
        log.error("gmail_send_error", to=to, subject=subject, error=str(exc))
        return {"error": str(exc)}


def format_emails_for_prompt(emails: list[dict], header: Optional[str] = None) -> str:
    """Render emails as plain text for a prompt."""
    if not emails:
        return "(no unread emails)"
    lines = []
    if header:
        lines.append(header)
    for e in emails:
        lines.append(f"• From: {e['from']} | Subject: {e['subject']} | {e['snippet'][:100]}")
    return "\n".join(lines)
