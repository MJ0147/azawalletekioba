from __future__ import annotations

import asyncio
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from statistics import mean
from typing import Any
from xml.etree import ElementTree

import httpx
import yfinance as yf

HTTP_TIMEOUT = 12.0
SERIES_LENGTH = 10
STOCK_SYMBOL = os.getenv("AGENT_STOCK_SYMBOL", os.getenv("DASHBOARD_STOCK_SYMBOL", "AAPL"))
CRYPTO_SYMBOL = os.getenv("AGENT_CRYPTO_SYMBOL", os.getenv("DASHBOARD_CRYPTO_SYMBOL", "BTCUSDT"))

DEFAULT_FORECAST_DATA: dict[str, dict[str, list[Any]]] = {
    "stocks": {
        "labels": ["Day 1", "Day 2", "Day 3"],
        "actual": [145, 147, 149],
        "predicted": [146, 148, 150],
    },
    "crypto": {
        "labels": ["Hour 1", "Hour 2", "Hour 3"],
        "actual": [32000, 32200, 32150],
        "predicted": [32300, 32400, 32500],
    },
    "sentiment": {
        "labels": ["Index"],
        "values": [65],
    },
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default


def _date_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %d %H:%M")
    return str(value)


def _predict_next(values: list[float], horizon: int = 3) -> list[float]:
    if not values:
        return [0.0] * horizon
    if len(values) == 1:
        return [values[0]] * horizon

    recent_window = values[-3:] if len(values) >= 3 else values
    base = mean(recent_window)
    trend = (values[-1] - values[0]) / max(len(values) - 1, 1)
    return [round(base + (trend * step), 2) for step in range(1, horizon + 1)]


def _empty_forecast() -> dict[str, list[float] | list[str]]:
    return {"labels": [], "actual": [], "predicted": []}


def _empty_series() -> dict[str, list[float] | list[str]]:
    return {"labels": [], "values": []}


def get_stock_data(symbol: str = STOCK_SYMBOL) -> dict[str, list[float] | list[str]]:
    try:
        data = yf.download(symbol, period="5d", interval="1h", progress=False, auto_adjust=False)
        closes = data.get("Close")
        if closes is None or closes.empty:
            return _empty_forecast()

        closes_list = [_safe_float(value) for value in closes.tolist()[-SERIES_LENGTH:]]
        labels = [_date_label(value.to_pydatetime()) for value in closes.index.tolist()[-SERIES_LENGTH:]]
        return {"labels": labels, "actual": closes_list, "predicted": _predict_next(closes_list)}
    except Exception:
        return _empty_forecast()


async def fetch_stock_data(symbol: str = STOCK_SYMBOL) -> dict[str, list[float] | list[str]]:
    return await asyncio.to_thread(get_stock_data, symbol)


def get_crypto_data(symbol: str = CRYPTO_SYMBOL) -> dict[str, list[float] | list[str]]:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": symbol, "interval": "1h", "limit": SERIES_LENGTH},
            )
        response.raise_for_status()
        payload = response.json()
        closes = [_safe_float(item[4]) for item in payload]
        labels = [datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.utc).strftime("%b %d %H:%M") for item in payload]
        return {"labels": labels, "actual": closes, "predicted": _predict_next(closes)}
    except Exception:
        return _empty_forecast()


async def fetch_crypto_data(symbol: str = CRYPTO_SYMBOL) -> dict[str, list[float] | list[str]]:
    return await asyncio.to_thread(get_crypto_data, symbol)


def get_sosovalue_sentiment() -> dict[str, list[float] | list[str]]:
    """Fetch crypto market sentiment from SoSoValue; tries multiple known endpoints."""
    _SOSO_ENDPOINTS = [
        "https://api.sosovalue.com/crypto/index",
        "https://sosovalue.com/api/fear-and-greed",
        "https://api.alternative.me/fng/?limit=1&format=json",  # fallback: Fear & Greed
    ]
    for url in _SOSO_ENDPOINTS:
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
            # SoSoValue returns {"sentiment": <float>} or {"data":[{"value":"<int>"}]}
            value = payload.get("sentiment") or payload.get("index") or payload.get("score")
            if value is None:
                data_list = payload.get("data", [])
                if isinstance(data_list, list) and data_list:
                    value = data_list[0].get("value")
            if value is not None:
                return {"labels": ["Sentiment"], "values": [_safe_float(value, 50.0)]}
        except Exception:
            continue
    return {"labels": ["Sentiment"], "values": [50.0]}


def get_google_finance_signal() -> float:
    """Blended sentiment signal from Google Finance + Yahoo Finance RSS headlines."""
    feeds = [
        "https://news.google.com/rss/search?q=stock+market+crypto+bitcoin&hl=en-US&gl=US&ceid=US:en",
        "https://finance.yahoo.com/news/rssindex",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD,AAPL,SPY&region=US&lang=en-US",
    ]
    bullish = {"surge", "gain", "rally", "beat", "growth", "high", "bull", "up", "rise", "record", "jump", "soar"}
    bearish = {"drop", "fall", "crash", "miss", "loss", "low", "bear", "down", "plunge", "slump", "sink", "decline"}
    all_titles: list[str] = []
    for rss_url in feeds:
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.get(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code >= 400:
                continue
            root = ElementTree.fromstring(response.text)
            titles = [
                item.findtext("title", default="")
                for item in root.findall("./channel/item")[:15]
            ]
            all_titles.extend(titles)
        except Exception:
            continue

    if not all_titles:
        return 50.0

    score = 50.0
    for title in all_titles:
        tokens = set(re.findall(r"[a-zA-Z]+", title.lower()))
        if tokens & bullish:
            score += 1.5
        if tokens & bearish:
            score -= 1.5

    return max(0.0, min(100.0, round(score, 2)))


def _get_yahoo_finance_price(ticker: str) -> float | None:
    """Fetch latest close price for a ticker from Yahoo Finance quote summary."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        with httpx.Client(timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = client.get(url)
        r.raise_for_status()
        payload = r.json()
        meta = payload.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        return _safe_float(price) if price is not None else None
    except Exception:
        return None


async def fetch_sentiment_data() -> dict[str, list[float] | list[str]]:
    soso, google_value = await asyncio.gather(
        asyncio.to_thread(get_sosovalue_sentiment),
        asyncio.to_thread(get_google_finance_signal),
    )
    soso_value = _safe_float((soso.get("values") or [50])[0], 50.0)
    blended = round((0.65 * soso_value) + (0.35 * google_value), 2)
    return {
        "labels": ["Market"],
        "values": [blended],
        "components": {
            "sosovalue": soso_value,
            "google_finance_signal": google_value,
        },
        "sources": [
            "https://www.sosovalue.com/",
            "https://www.google.com/finance",
            "https://finance.yahoo.com/",
        ],
    }


# Rolling window of Supabase round-trip latencies for the dashboard's
# "Supabase health" card: one probe per dashboard refresh, newest last.
_supabase_latency: deque[tuple[str, float]] = deque(maxlen=SERIES_LENGTH)


def get_supabase_health() -> dict[str, Any]:
    """Time one round trip to the project's Auth health endpoint."""
    try:
        from services import supabase_client
    except Exception:
        return {**_empty_series(), "status": "unavailable"}

    url, key = supabase_client.SUPABASE_URL, supabase_client.SUPABASE_KEY
    if not url or not key:
        return {**_empty_series(), "status": "not-configured"}

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(f"{url}/auth/v1/health", headers={"apikey": key})
        latency_ms = _safe_float((time.perf_counter() - started) * 1000)
        status = "healthy" if response.status_code < 400 else f"http-{response.status_code}"
        _supabase_latency.append(
            (datetime.now(timezone.utc).strftime("%b %d %H:%M:%S"), latency_ms)
        )
    except httpx.HTTPError:
        status = "unreachable"

    return {
        "labels": [label for label, _ in _supabase_latency],
        "values": [value for _, value in _supabase_latency],
        "status": status,
    }


async def fetch_cloud_data() -> dict[str, Any]:
    return await asyncio.to_thread(get_supabase_health)


async def build_dashboard_forecast() -> dict[str, Any]:
    stocks, crypto, sentiment, cloud = await asyncio.gather(
        fetch_stock_data(),
        fetch_crypto_data(),
        fetch_sentiment_data(),
        fetch_cloud_data(),
    )

    # Verify / enrich stock data with a live Yahoo Finance spot price
    yf_price = await asyncio.to_thread(_get_yahoo_finance_price, STOCK_SYMBOL)
    if yf_price and stocks.get("actual"):
        # Append the live spot as the final actual data point if it differs
        last_actual = stocks["actual"][-1] if stocks["actual"] else 0
        if abs(yf_price - last_actual) / max(last_actual, 1) > 0.001:  # >0.1% drift
            stocks["actual"].append(yf_price)
            stocks["labels"].append("Live")
            stocks["predicted"] = _predict_next(stocks["actual"])

    return {
        "stocks": stocks,
        "crypto": crypto,
        "sentiment": sentiment,
        "cloud": cloud,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_urls": {
            "stocks": ["https://finance.yahoo.com/", "https://query1.finance.yahoo.com/"],
            "crypto": ["https://api.binance.com/", "https://www.sosovalue.com/", "https://finance.yahoo.com/"],
            "sentiment": sentiment.get("sources", [
                "https://www.sosovalue.com/",
                "https://www.google.com/finance",
                "https://finance.yahoo.com/",
            ]),
        },
    }


async def get_dashboard_forecast() -> dict[str, Any]:
    try:
        forecast = await build_dashboard_forecast()

        # Ensure frontend charts always receive usable datasets.
        if not forecast.get("stocks", {}).get("labels"):
            forecast["stocks"] = DEFAULT_FORECAST_DATA["stocks"]
        if not forecast.get("crypto", {}).get("labels"):
            forecast["crypto"] = DEFAULT_FORECAST_DATA["crypto"]
        if not forecast.get("sentiment", {}).get("labels"):
            forecast["sentiment"] = DEFAULT_FORECAST_DATA["sentiment"]

        return forecast
    except Exception:
        return {
            "stocks": DEFAULT_FORECAST_DATA["stocks"],
            "crypto": DEFAULT_FORECAST_DATA["crypto"],
            "sentiment": DEFAULT_FORECAST_DATA["sentiment"],
            "cloud": _empty_series(),
        }