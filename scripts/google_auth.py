"""
One-time Google Calendar OAuth2 setup.

Run this locally to authorize WorkLife to read your Google Calendar.
After completing the flow, copy the printed env vars into your .env and Railway settings.

Usage:
    uv run python -m scripts.google_auth

Prerequisites:
    1. Go to https://console.cloud.google.com/
    2. Create a project (or use an existing one)
    3. Enable the Google Calendar API
    4. Create OAuth 2.0 credentials (type: Desktop app)
    5. Download the credentials JSON
    6. Set GOOGLE_CREDENTIALS_JSON=<contents of that JSON> in your .env
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow
    import google.oauth2.credentials

    credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if not credentials_json:
        print("ERROR: GOOGLE_CREDENTIALS_JSON is not set in your .env")
        print("  Download OAuth2 Desktop credentials from Google Cloud Console and set the env var.")
        sys.exit(1)

    creds_data = json.loads(credentials_json)

    # google_auth_oauthlib expects the JSON in a file; write to a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(creds_data, f)
        tmp_path = f.name

    try:
        flow = InstalledAppFlow.from_client_secrets_file(tmp_path, _SCOPES)
        creds = flow.run_local_server(port=0)
    finally:
        os.unlink(tmp_path)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    token_json = json.dumps(token_data)

    print("\n=== SUCCESS ===")
    print("Add this to your .env and Railway environment variables:\n")
    print(f'GOOGLE_TOKEN_JSON={token_json}')
    print("\nDone. WorkLife can now read your Google Calendar.")


if __name__ == "__main__":
    main()
