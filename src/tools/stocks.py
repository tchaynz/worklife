"""Alpha Vantage API — fetch stock price and basic data for Ted's positions."""
from __future__ import annotations

import httpx

from src.config import settings
from src.utils.logger import log

_BASE_URL = "https://www.alphavantage.co/query"
_TIMEOUT = 10.0

# Ted's stock positions
POSITIONS = ["SMCI"]


async def get_stock_quote(symbol: str) -> dict | None:
    """Fetch the current quote for a stock symbol.

    Returns:
        {
            "symbol": "SMCI",
            "price_usd": 42.50,
            "change_pct": -2.3,
            "volume": 12345678,
        }
        or None on error / rate limit.
    """
    if not settings.alpha_vantage_api_key:
        log.warning("alpha_vantage_key_missing")
        return None

    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": settings.alpha_vantage_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        log.error("alpha_vantage_error", symbol=symbol, error=str(exc))
        return None

    quote = data.get("Global Quote", {})
    if not quote or "05. price" not in quote:
        log.warning("alpha_vantage_empty_response", symbol=symbol, raw=str(data)[:200])
        return None

    try:
        price = float(quote["05. price"])
        change_pct = float(quote["10. change percent"].strip("%"))
        volume = int(quote["06. volume"])
    except (KeyError, ValueError) as exc:
        log.error("alpha_vantage_parse_error", symbol=symbol, error=str(exc))
        return None

    log.info("stock_quote_fetched", symbol=symbol, price=price)
    return {
        "symbol": symbol,
        "price_usd": price,
        "change_pct": round(change_pct, 2),
        "volume": volume,
    }


async def get_all_stock_quotes() -> dict[str, dict]:
    """Fetch quotes for all of Ted's stock positions."""
    import asyncio
    results = await asyncio.gather(*[get_stock_quote(s) for s in POSITIONS])
    return {s: r for s, r in zip(POSITIONS, results) if r is not None}
