"""CoinGecko API — fetch current prices for Ted's crypto positions."""
from __future__ import annotations

import httpx

from src.config import settings
from src.utils.logger import log

# Maps ticker symbol → CoinGecko coin ID
COIN_IDS: dict[str, str] = {
    "XRP": "ripple",
    "XLM": "stellar",
    "FET": "fetch-ai",
    "LINK": "chainlink",
    "SOL": "solana",
}

_BASE_URL = "https://api.coingecko.com/api/v3"
_TIMEOUT = 10.0


async def get_crypto_prices(symbols: list[str] | None = None) -> dict[str, dict]:
    """Fetch current USD prices and 24h change for one or more coins.

    Args:
        symbols: List of ticker symbols (e.g. ["XRP", "SOL"]).
                 Defaults to all of Ted's positions.

    Returns:
        {
            "XRP": {"price_usd": 0.52, "change_24h_pct": 3.1},
            "SOL": {"price_usd": 148.0, "change_24h_pct": -1.2},
            ...
        }
        Missing or errored coins are omitted from the result.
    """
    targets = symbols or list(COIN_IDS.keys())
    coin_ids = [COIN_IDS[s] for s in targets if s in COIN_IDS]

    if not coin_ids:
        return {}

    params: dict = {
        "ids": ",".join(coin_ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE_URL}/simple/price", params=params, headers=headers)
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPError as exc:
        log.error("coingecko_error", error=str(exc))
        return {}

    # Build symbol-keyed result
    id_to_symbol = {v: k for k, v in COIN_IDS.items()}
    result: dict[str, dict] = {}
    for coin_id, data in raw.items():
        symbol = id_to_symbol.get(coin_id)
        if symbol:
            result[symbol] = {
                "price_usd": data.get("usd", 0.0),
                "change_24h_pct": round(data.get("usd_24h_change", 0.0), 2),
            }

    log.info("crypto_prices_fetched", symbols=list(result.keys()))
    return result
