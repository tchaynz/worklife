#!/usr/bin/env python3
"""Simulate a Twilio WhatsApp webhook POST to test the echo endpoint locally.

Usage:
    python scripts/test_whatsapp.py
    python scripts/test_whatsapp.py "Custom message here"
"""
import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"
message = sys.argv[1] if len(sys.argv) > 1 else "Hello WorkLife"

print(f"Sending: {message!r}")
r = httpx.post(
    f"{BASE_URL}/webhook/whatsapp",
    timeout=60.0,
    data={
        "From": "whatsapp:+15555555555",
        "Body": message,
        "MessageSid": "SMtest123",
        "AccountSid": "ACtest",
    },
)
print(f"Status: {r.status_code}")
print(r.text)
