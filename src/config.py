from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""
    my_whatsapp_number: str = ""
    app_env: str = "development"
    log_level: str = "INFO"

    coingecko_api_key: str = ""
    alpha_vantage_api_key: str = ""

    # Google Calendar — set via scripts/google_auth.py (one-time OAuth setup)
    google_credentials_json: str = ""   # OAuth2 client secrets JSON (from Google Cloud Console)
    google_token_json: str = ""         # Serialized token (includes refresh_token)

    # MCP server — Bearer token for claude.ai integration
    mcp_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
