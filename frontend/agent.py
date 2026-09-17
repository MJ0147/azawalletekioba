"""Live market data for the dashboard, the wallet API and Iyobo's market answers.

Every number that reaches a visitor comes from a named source and carries the time it was
measured. Nothing here invents a price: when a provider can't be reached the series comes back
empty with `status: "unavailable"` and the reason, and the dashboard says so rather than drawing
a line through numbers nobody quoted.

Where the data comes from:
  * Stocks    Yahoo Finance's chart API (query1, then query2) — hourly closes plus the live quote.
  * Crypto    Binance, then Coinbase, then Kraken, then CoinGecko. The first one that answers wins,
              and the reply names it; Binance is blocked in some regions, so the chain matters.
  * Sentiment The Crypto Fear & Greed Index (alternative.me), published 0-100. Headline tone from
              Google News and Yahoo Finance is reported next to it as a separate, clearly marked
              keyword tally — it is a rough signal, not an index, so it is never blended in.
  * Cloud     One timed round trip to this project's Supabase auth health endpoint.

"Predicted" values are a least-squares trend line through the recent closes, extrapolated a few
steps. That is an extrapolation, not a forecast of the market, and every payload says so in
`method` so the dashboard and Iyobo can caveat it honestly.

Results are cached for MARKET_CACHE_SECONDS (default 60) so a busy page or a chat burst doesn't
hammer the providers and earn a rate limit.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Sequence
from xml.etree import ElementTree

import httpx

logger = logging.getLogger("ekioba.market")

HTTP_TIMEOUT = float(os.getenv("MARKET_HTTP_TIMEOUT", "12"))
SERIES_LENGTH = 10
HORIZON = 3
CACHE_SECONDS = float(os.getenv("MARKET_CACHE_SECONDS", "60"))
SENTIMENT_CACHE_SECONDS = float(os.getenv("MARKET_SENTIMENT_CACHE_SECONDS", "600"))
USER_AGENT = "Mozilla/5.0 (compatible; EKIOBA/1.0; +https://ekioba.com)"

STOCK_SYMBOL = os.getenv("AGENT_STOCK_SYMBOL", os.getenv("DASHBOARD_STOCK_SYMBOL", "AAPL"))
CRYPTO_SYMBOL = os.getenv("AGENT_CRYPTO_SYMBOL", os.getenv("DASHBOARD_CRYPTO_SYMBOL", "BTCUSDT"))

TREND_METHOD = "Least-squares trend through the closes shown, extrapolated 3 steps. Not investment advice."

# CoinGecko needs a coin id rather than a trading pair. Anything not listed falls back to the
# lowercased base symbol, which is right for many coins and simply misses for the rest.
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "TON": "the-open-network",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
}
# Kraken's own names for a few assets.
KRAKEN_ASSETS = {"BTC": "XBT", "DOGE": "XDG"}
# Stablecoin quotes are priced 1:1 with the dollar on venues that don't list them.
STABLE_QUOTES = {"USDT", "USDC", "BUSD", "DAI", "TUSD"}
QUOTE_SYMBOLS = ("USDT", "USDC", "BUSD", "USD", "EUR", "GBP", "NGN", "BTC", "ETH")


# ── Shapes ──────────────────────────────────────────────────────────────────


def empty_series(reason: str = "") -> dict[str, Any]:
    """A price series nobody could measure. The dashboard renders this as 'unavailable'."""
    return {
        "labels": [],
        "actual": [],
        "predicted": [],
        "predicted_labels": [],
        "status": "unavailable",
        "error": reason or "No market data provider could be reached.",
    }


def _empty_values(reason: str = "") -> dict[str, Any]:
    return {
        "labels": [],
        "values": [],
        "status": "unavailable",
        "error": reason or "No data.",
    }


def unavailable_forecast(reason: str = "") -> dict[str, Any]:
    """The whole payload when nothing could be fetched. Used by app.py as its own fallback."""
    return {
        "stocks": empty_series(reason),
        "crypto": empty_series(reason),
        "sentiment": _empty_values(reason),
        "cloud": _empty_values(reason),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "unavailable",
    }


# ── Numbers ─────────────────────────────────────────────────────────────────


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return default
    return round(number, 2)


def _label(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%b %d %H:%M")


def _from_millis(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _from_seconds(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _trend(values: Sequence[float], horizon: int = HORIZON) -> tuple[list[float], float]:
    """Extrapolate a least-squares line through `values`. Returns the points and the fit's r².

    A straight line is the honest shape for this: it states "the recent slope, continued", which is
    what the dashboard's caption claims. r² says how well that line actually describes the closes,
    so a noisy series can be shown as the weak signal it is.
    """
    points = [float(value) for value in values]
    if not points:
        return [], 0.0
    if len(points) == 1:
        return [round(points[0], 2)] * horizon, 0.0

    n = len(points)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(points) / n
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    if variance_x == 0:
        return [round(mean_y, 2)] * horizon, 0.0

    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, points)) / variance_x
    intercept = mean_y - slope * mean_x

    total_variance = sum((y - mean_y) ** 2 for y in points)
    residuals = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, points))
    r_squared = 1.0 - (residuals / total_variance) if total_variance else 0.0

    # A price can approach zero but never pass it, however steep the recent slope.
    projected = [max(0.0, slope * (n - 1 + step) + intercept) for step in range(1, horizon + 1)]
    return [round(value, 2) for value in projected], round(max(0.0, min(1.0, r_squared)), 3)


def _step_labels(moments: Sequence[datetime], horizon: int = HORIZON) -> list[str]:
    """Labels for the extrapolated points, one interval apart from the last close."""
    if len(moments) < 2:
        return [f"+{step}" for step in range(1, horizon + 1)]
    interval = moments[-1] - moments[-2]
    return [_label(moments[-1] + interval * step) for step in range(1, horizon + 1)]


def _series(
    moments: Sequence[datetime],
    closes: Sequence[float],
    *,
    source: str,
    symbol: str,
    currency: str = "USD",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one provider's closes into the payload the dashboard draws."""
    moments = list(moments[-SERIES_LENGTH:])
    closes = [round(float(close), 2) for close in closes[-SERIES_LENGTH:]]
    predicted, r_squared = _trend(closes)
    payload: dict[str, Any] = {
        "labels": [_label(moment) for moment in moments],
        "actual": closes,
        "predicted": predicted,
        "predicted_labels": _step_labels(moments),
        "latest": closes[-1] if closes else None,
        "symbol": symbol,
        "currency": currency,
        "source": source,
        "as_of": moments[-1].isoformat() if moments else None,
        "method": TREND_METHOD,
        "trend_fit": r_squared,
        "status": "ok",
    }
    if len(closes) >= 2 and closes[0]:
        payload["change_percent"] = round((closes[-1] - closes[0]) / closes[0] * 100, 2)
    if extra:
        payload.update(extra)
    return payload


# ── HTTP ────────────────────────────────────────────────────────────────────


async def _get_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


async def _first_success(
    providers: Iterable[tuple[str, Callable[[], Awaitable[dict[str, Any]]]]],
) -> dict[str, Any]:
    """Try each provider in turn; return the first usable series, else an empty one naming the failures."""
    failures: list[str] = []
    for name, fetch in providers:
        try:
            series = await fetch()
        except Exception as exc:  # a provider being down must not take the dashboard with it
            failures.append(f"{name}: {exc.__class__.__name__}")
            logger.warning("Market provider %s failed: %r", name, exc)
            continue
        if series.get("actual"):
            return series
        failures.append(f"{name}: no data")
    return empty_series(f"Tried {', '.join(failures)}." if failures else "")


# ── Stocks: Yahoo Finance ───────────────────────────────────────────────────


def _parse_yahoo_chart(payload: Any, symbol: str) -> dict[str, Any]:
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        raise ValueError("Yahoo Finance returned no result")
    block = result[0]
    meta = block.get("meta") or {}
    timestamps = block.get("timestamp") or []
    quote = ((block.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []

    # Yahoo pads the session with nulls where no trade printed in that bucket.
    pairs = [
        (_from_seconds(stamp), float(close))
        for stamp, close in zip(timestamps, closes)
        if close is not None
    ]
    if not pairs:
        raise ValueError("Yahoo Finance returned no closes")

    spot = _safe_float(meta.get("regularMarketPrice"), None)
    quoted_at = meta.get("regularMarketTime")
    if spot is not None and quoted_at:
        moment = _from_seconds(quoted_at)
        interval = (pairs[-1][0] - pairs[-2][0]) if len(pairs) >= 2 else None
        if interval and moment - pairs[-1][0] >= interval:
            pairs.append((moment, spot))  # a bar has closed since; the quote is a new point
        elif moment >= pairs[-1][0]:
            pairs[-1] = (moment, spot)  # still inside the last bar; the quote is its latest price

    moments = [moment for moment, _ in pairs]
    prices = [price for _, price in pairs]
    extra = {
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "source_url": f"https://finance.yahoo.com/quote/{symbol}",
    }
    if meta.get("marketState"):
        extra["market_state"] = meta["marketState"]
    day_change = _safe_float(meta.get("regularMarketChangePercent"), None)
    if day_change is not None:
        extra["day_change_percent"] = day_change
    return _series(
        moments,
        prices,
        source="Yahoo Finance",
        symbol=symbol,
        currency=str(meta.get("currency") or "USD"),
        extra=extra,
    )


async def fetch_stock_data(symbol: str = STOCK_SYMBOL) -> dict[str, Any]:
    """Hourly closes for `symbol` over the last five sessions, plus the live quote."""

    def provider(host: str) -> Callable[[], Awaitable[dict[str, Any]]]:
        async def fetch() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                payload = await _get_json(
                    client,
                    f"https://{host}/v8/finance/chart/{symbol}",
                    params={"interval": "1h", "range": "5d", "includePrePost": "false"},
                )
            return _parse_yahoo_chart(payload, symbol)

        return fetch

    # query2 is the same service on a second host; it answers when query1 is throttled.
    return await _first_success(
        [("Yahoo Finance", provider("query1.finance.yahoo.com")),
         ("Yahoo Finance (query2)", provider("query2.finance.yahoo.com"))]
    )


# ── Crypto: Binance, Coinbase, Kraken, CoinGecko ────────────────────────────


def _split_pair(symbol: str) -> tuple[str, str]:
    """"BTCUSDT" -> ("BTC", "USDT"). Falls back to a USDT quote for a bare asset name."""
    upper = re.sub(r"[^A-Z0-9]", "", symbol.upper())
    for quote in QUOTE_SYMBOLS:
        if upper.endswith(quote) and len(upper) > len(quote):
            return upper[: -len(quote)], quote
    return upper, "USDT"


def _fiat_quote(quote: str) -> str:
    return "USD" if quote in STABLE_QUOTES else quote


async def _binance(symbol: str, base: str, quote: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        payload = await _get_json(
            client,
            "https://api.binance.com/api/v3/klines",
            params={"symbol": f"{base}{quote}", "interval": "1h", "limit": SERIES_LENGTH},
        )
    if not isinstance(payload, list) or not payload:
        raise ValueError("Binance returned no candles")
    # Each kline is [open time, open, high, low, close, volume, close time, ...].
    moments = [_from_millis(candle[6]) for candle in payload]
    closes = [float(candle[4]) for candle in payload]
    return _series(
        moments, closes, source="Binance", symbol=f"{base}{quote}", currency=_fiat_quote(quote),
        extra={"source_url": f"https://www.binance.com/en/trade/{base}_{quote}"},
    )


async def _coinbase(symbol: str, base: str, quote: str) -> dict[str, Any]:
    product = f"{base}-{_fiat_quote(quote)}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        payload = await _get_json(
            client,
            f"https://api.exchange.coinbase.com/products/{product}/candles",
            params={"granularity": 3600},
        )
    if not isinstance(payload, list) or not payload:
        raise ValueError("Coinbase returned no candles")
    # [time, low, high, open, close, volume], newest first.
    candles = sorted(payload, key=lambda candle: candle[0])[-SERIES_LENGTH:]
    moments = [_from_seconds(candle[0]) for candle in candles]
    closes = [float(candle[4]) for candle in candles]
    return _series(
        moments, closes, source="Coinbase", symbol=product, currency=_fiat_quote(quote),
        extra={"source_url": f"https://www.coinbase.com/price/{base.lower()}"},
    )


async def _kraken(symbol: str, base: str, quote: str) -> dict[str, Any]:
    pair = f"{KRAKEN_ASSETS.get(base, base)}{_fiat_quote(quote)}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        payload = await _get_json(
            client, "https://api.kraken.com/0/public/OHLC", params={"pair": pair, "interval": 60}
        )
    errors = (payload or {}).get("error") or []
    if errors:
        raise ValueError(f"Kraken: {errors[0]}")
    result = (payload or {}).get("result") or {}
    # Kraken names the series with its own asset codes (XXBTZUSD), alongside a "last" cursor.
    candles = next((value for key, value in result.items() if key != "last" and isinstance(value, list)), [])
    if not candles:
        raise ValueError("Kraken returned no candles")
    candles = candles[-SERIES_LENGTH:]
    moments = [_from_seconds(candle[0]) for candle in candles]
    closes = [float(candle[4]) for candle in candles]
    return _series(
        moments, closes, source="Kraken", symbol=pair, currency=_fiat_quote(quote),
        extra={"source_url": f"https://www.kraken.com/prices/{base.lower()}"},
    )


async def _coingecko(symbol: str, base: str, quote: str) -> dict[str, Any]:
    coin_id = COINGECKO_IDS.get(base, base.lower())
    currency = _fiat_quote(quote)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        payload = await _get_json(
            client,
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            # 2 days is where CoinGecko switches to hourly points, which is what the chart wants.
            params={"vs_currency": currency.lower(), "days": 2},
        )
    prices = (payload or {}).get("prices") or []
    if not prices:
        raise ValueError("CoinGecko returned no prices")
    points = prices[-SERIES_LENGTH:]
    moments = [_from_millis(point[0]) for point in points]
    closes = [float(point[1]) for point in points]
    return _series(
        moments, closes, source="CoinGecko", symbol=f"{base}{currency}", currency=currency,
        extra={"source_url": f"https://www.coingecko.com/en/coins/{coin_id}"},
    )


async def fetch_crypto_data(symbol: str = CRYPTO_SYMBOL) -> dict[str, Any]:
    """Hourly closes for `symbol` from the first exchange that answers.

    Binance is first because it is the deepest market for these pairs, but it refuses some regions
    outright, so Coinbase, Kraken and CoinGecko stand behind it.
    """
    base, quote = _split_pair(symbol)
    return await _first_success(
        [
            ("Binance", lambda: _binance(symbol, base, quote)),
            ("Coinbase", lambda: _coinbase(symbol, base, quote)),
            ("Kraken", lambda: _kraken(symbol, base, quote)),
            ("CoinGecko", lambda: _coingecko(symbol, base, quote)),
        ]
    )


# ── Cache ───────────────────────────────────────────────────────────────────

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


def _cached(key: str, ttl: float) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None


# ── Sentiment ───────────────────────────────────────────────────────────────

BULLISH = {"surge", "gain", "gains", "rally", "beat", "beats", "growth", "high", "highs", "bull",
           "bullish", "rise", "rises", "record", "jump", "jumps", "soar", "soars", "climb", "climbs"}
BEARISH = {"drop", "drops", "fall", "falls", "crash", "miss", "misses", "loss", "losses", "low",
           "lows", "bear", "bearish", "plunge", "plunges", "slump", "sink", "sinks", "decline",
           "declines", "tumble", "tumbles", "selloff"}

NEWS_FEEDS = (
    "https://news.google.com/rss/search?q=stock+market+crypto+bitcoin&hl=en-US&gl=US&ceid=US:en",
    "https://finance.yahoo.com/news/rssindex",
)


async def fetch_fear_and_greed() -> dict[str, Any]:
    """The Crypto Fear & Greed Index, 0 (extreme fear) to 100 (extreme greed)."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        payload = await _get_json(client, "https://api.alternative.me/fng/", params={"limit": 1, "format": "json"})
    entries = (payload or {}).get("data") or []
    if not entries:
        raise ValueError("No index value returned")
    entry = entries[0]
    value = _safe_float(entry.get("value"), None)
    if value is None:
        raise ValueError("Index value was not a number")
    return {
        "labels": ["Fear & Greed"],
        "values": [value],
        "classification": str(entry.get("value_classification") or "").strip() or None,
        "as_of": _from_seconds(entry.get("timestamp")).isoformat() if entry.get("timestamp") else None,
        "source": "Crypto Fear & Greed Index (alternative.me)",
        "source_url": "https://alternative.me/crypto/fear-and-greed-index/",
        "status": "ok",
    }


async def fetch_news_tone() -> dict[str, Any]:
    """A keyword tally over market headlines: a rough mood signal, not an index.

    It is reported beside the Fear & Greed Index rather than mixed into it, because counting
    words in headlines is not a measurement anyone publishes.
    """
    titles: list[str] = []
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        for url in NEWS_FEEDS:
            try:
                response = await client.get(url)
                response.raise_for_status()
                root = ElementTree.fromstring(response.text)
            except Exception as exc:
                logger.info("Headline feed unavailable (%s): %s", url, exc.__class__.__name__)
                continue
            titles.extend(item.findtext("title", default="") for item in root.findall("./channel/item")[:15])

    if not titles:
        return {"status": "unavailable", "error": "No headline feed could be read."}

    score = 50.0
    for title in titles:
        words = set(re.findall(r"[a-zA-Z]+", title.lower()))
        if words & BULLISH:
            score += 1.5
        if words & BEARISH:
            score -= 1.5
    return {
        "score": round(max(0.0, min(100.0, score)), 2),
        "headlines": len(titles),
        "method": "Keyword tally over Google News and Yahoo Finance market headlines. A rough signal, not an index.",
        "sources": ["https://news.google.com/", "https://finance.yahoo.com/"],
        "status": "ok",
    }


async def fetch_sentiment_data() -> dict[str, Any]:
    """The index and the headline tone, cached longer than prices: both move by the day, not the minute."""
    hit = _cached("sentiment", SENTIMENT_CACHE_SECONDS)
    if hit is not None:
        return hit

    index, tone = await asyncio.gather(
        fetch_fear_and_greed(), fetch_news_tone(), return_exceptions=True
    )
    if isinstance(index, Exception):
        logger.warning("Fear & Greed Index unavailable: %s", index)
        sentiment = _empty_values("The Crypto Fear & Greed Index could not be reached.")
    else:
        sentiment = index
    sentiment["news_tone"] = {"status": "unavailable"} if isinstance(tone, Exception) else tone
    if sentiment.get("status") == "ok":
        _cache["sentiment"] = (time.monotonic(), sentiment)
    return sentiment


# ── Supabase health ─────────────────────────────────────────────────────────

# Rolling window of Supabase round-trip latencies for the dashboard's "Supabase health" card:
# one probe per dashboard refresh, newest last.
_supabase_latency: deque[tuple[str, float]] = deque(maxlen=SERIES_LENGTH)


async def fetch_cloud_data() -> dict[str, Any]:
    """Time one round trip to the project's Supabase auth health endpoint."""
    try:
        from services import supabase_client
    except Exception:
        return {**_empty_values("Supabase client is not installed."), "status": "unavailable"}

    url, key = supabase_client.SUPABASE_URL, supabase_client.SUPABASE_KEY
    if not url or not key:
        return {**_empty_values("Supabase is not configured."), "status": "not-configured"}

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(f"{url}/auth/v1/health", headers={"apikey": key})
        latency_ms = _safe_float((time.perf_counter() - started) * 1000)
        status = "healthy" if response.status_code < 400 else f"http-{response.status_code}"
        _supabase_latency.append((datetime.now(timezone.utc).strftime("%b %d %H:%M:%S"), latency_ms))
    except httpx.HTTPError as exc:
        logger.warning("Supabase health probe failed: %s", exc.__class__.__name__)
        status = "unreachable"

    return {
        "labels": [label for label, _ in _supabase_latency],
        "values": [value for _, value in _supabase_latency],
        "status": status,
        "unit": "ms",
    }


# ── The dashboard payload ───────────────────────────────────────────────────


async def build_dashboard_forecast() -> dict[str, Any]:
    """Fetch every panel in parallel. A panel that fails says so; it never borrows another's numbers."""
    stocks, crypto, sentiment, cloud = await asyncio.gather(
        fetch_stock_data(),
        fetch_crypto_data(),
        fetch_sentiment_data(),
        fetch_cloud_data(),
        return_exceptions=True,
    )

    def settled(result: Any, name: str, empty: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
        if isinstance(result, Exception):
            logger.warning("%s panel failed: %s", name, result)
            return empty(f"{name} data could not be loaded.")
        return result

    stocks = settled(stocks, "Stock", empty_series)
    crypto = settled(crypto, "Crypto", empty_series)
    sentiment = settled(sentiment, "Sentiment", _empty_values)
    cloud = settled(cloud, "Cloud", _empty_values)

    live = [panel for panel in (stocks, crypto, sentiment) if panel.get("status") == "ok"]
    sources = [panel["source"] for panel in (stocks, crypto, sentiment) if panel.get("source")]
    return {
        "stocks": stocks,
        "crypto": crypto,
        "sentiment": sentiment,
        "cloud": cloud,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "status": "ok" if live else "unavailable",
    }


async def get_dashboard_forecast() -> dict[str, Any]:
    """The dashboard payload, refetched at most once every MARKET_CACHE_SECONDS.

    Only a payload with live panels is cached: a failed fetch is retried on the next request
    rather than pinning an "unavailable" dashboard in place for the whole window.
    """
    hit = _cached("forecast", CACHE_SECONDS)
    if hit is not None:
        return hit

    async with _cache_lock:
        # Another request may have refreshed it while this one waited for the lock.
        hit = _cached("forecast", CACHE_SECONDS)
        if hit is not None:
            return hit
        try:
            payload = await build_dashboard_forecast()
        except Exception as exc:
            logger.exception("Market data could not be assembled: %s", exc)
            return unavailable_forecast("Market data could not be assembled.")
        if payload.get("status") == "ok":
            _cache["forecast"] = (time.monotonic(), payload)
        return payload


def clear_cache() -> None:
    """Drop cached market data. For tests and for a forced refresh."""
    _cache.clear()
