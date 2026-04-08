"""Google Calendar API — read Ted's upcoming events."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/Toronto")

from src.config import settings
from src.utils.logger import log

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]
_CALENDAR_ID = "primary"


def _build_service():
    """Build an authenticated Google Calendar service (sync)."""
    import google.oauth2.credentials
    import googleapiclient.discovery

    if not settings.google_token_json or not settings.google_credentials_json:
        raise RuntimeError("Google Calendar credentials not configured. Run scripts/google_auth.py first.")

    token_data = json.loads(settings.google_token_json)
    creds_data = json.loads(settings.google_credentials_json)

    # Support both "installed" and "web" credential types
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
        "calendar", "v3", credentials=creds, cache_discovery=False
    )


def _fetch_events_sync(time_min: datetime, time_max: datetime, max_results: int = 20) -> list[dict]:
    """Synchronous calendar fetch — call via asyncio.to_thread."""
    service = _build_service()
    result = (
        service.events()
        .list(
            calendarId=_CALENDAR_ID,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def _parse_event(event: dict) -> dict:
    """Normalize a Calendar API event into a clean dict."""
    start = event.get("start", {})
    end = event.get("end", {})

    # All-day events use "date"; timed events use "dateTime"
    start_str = start.get("dateTime") or start.get("date", "")
    end_str = end.get("dateTime") or end.get("date", "")
    all_day = "dateTime" not in start

    return {
        "summary": event.get("summary", "(No title)"),
        "start": start_str,
        "end": end_str,
        "all_day": all_day,
        "location": event.get("location", ""),
        "description": (event.get("description") or "")[:200],
        "attendees": [
            a.get("email", "") for a in event.get("attendees", []) if not a.get("self")
        ],
    }


def _format_event_for_prompt(event: dict) -> str:
    """Render a single event as a one-liner for inclusion in a prompt."""
    if event["all_day"]:
        time_str = "All day"
    else:
        try:
            dt = datetime.fromisoformat(event["start"])
            # Convert to ET (UTC-4 summer / UTC-5 winter — approximate)
            dt_et = dt.astimezone(timezone(timedelta(hours=-4)))
            time_str = dt_et.strftime("%-I:%M %p")
        except ValueError:
            time_str = event["start"]

    line = f"• {time_str}: {event['summary']}"
    if event.get("location"):
        line += f" @ {event['location']}"
    if event.get("attendees"):
        line += f" (with {', '.join(event['attendees'][:3])})"
    return line


async def get_events(time_min: datetime, time_max: datetime) -> list[dict]:
    """Fetch and parse Calendar events between two datetimes."""
    try:
        raw = await asyncio.to_thread(_fetch_events_sync, time_min, time_max)
    except Exception as exc:
        log.error("calendar_fetch_error", error=str(exc))
        return []
    events = [_parse_event(e) for e in raw]
    log.info("calendar_events_fetched", count=len(events))
    return events


async def get_todays_events() -> list[dict]:
    now = datetime.now(_ET)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return await get_events(start, end)


async def get_tomorrows_events() -> list[dict]:
    now = datetime.now(_ET)
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return await get_events(start, end)


async def get_weeks_events() -> list[dict]:
    now = datetime.now(_ET)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return await get_events(start, end)


def format_events_for_prompt(events: list[dict], header: Optional[str] = None) -> str:
    """Render a list of events as plain text for a system prompt or response."""
    if not events:
        return "(no events)"
    lines = []
    if header:
        lines.append(header)
    lines.extend(_format_event_for_prompt(e) for e in events)
    return "\n".join(lines)
