from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

import httpx
import yfinance as yf

HTTP_TIMEOUT = 12.0
SERIES_LENGTH = 10
STOCK_SYMBOL = os.getenv("AGENT_STOCK_SYMBOL", os.getenv("DASHBOARD_STOCK_SYMBOL", "AAPL"))
CRYPTO_SYMBOL = os.getenv("AGENT_CRYPTO_SYMBOL", os.getenv("DASHBOARD_CRYPTO_SYMBOL", "BTCUSDT"))
AZURE_ACCESS_TOKEN = os.getenv("AZURE_ACCESS_TOKEN", "")
AZURE_VM_RESOURCE_ID = os.getenv("AZURE_VM_RESOURCE_ID", "")
AZURE_HEADERS = {"Authorization": f"Bearer {AZURE_ACCESS_TOKEN}"} if AZURE_ACCESS_TOKEN else {}

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


def _safe_float(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


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
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get("https://api.sosovalue.com/crypto/index")
        response.raise_for_status()
        payload = response.json()
        sentiment = _safe_float(payload.get("sentiment", 50))
        return {"labels": ["Sentiment"], "values": [sentiment]}
    except Exception:
        return {"labels": ["Sentiment"], "values": [50.0]}


async def fetch_sentiment_data() -> dict[str, list[float] | list[str]]:
    return await asyncio.to_thread(get_sosovalue_sentiment)


def get_azure_metrics(resource_id: str = AZURE_VM_RESOURCE_ID) -> dict[str, list[float] | list[str]]:
    if not resource_id or not AZURE_HEADERS:
        return _empty_series()

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=SERIES_LENGTH)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(
                f"https://management.azure.com{resource_id}/providers/microsoft.insights/metrics",
                params={
                    "api-version": "2018-01-01",
                    "metricnames": "Percentage CPU",
                    "aggregation": "Average",
                    "interval": "PT1H",
                    "timespan": f"{start.isoformat()}/{now.isoformat()}",
                },
                headers=AZURE_HEADERS,
            )
        response.raise_for_status()
        payload = response.json()
        values = payload.get("value", [])
        if not values:
            return _empty_series()

        points = values[0].get("timeseries", [])
        if not points:
            return _empty_series()

        data_points = points[0].get("data", [])[-SERIES_LENGTH:]
        labels = [
            datetime.fromisoformat(item["timeStamp"].replace("Z", "+00:00")).strftime("%b %d %H:%M")
            for item in data_points
            if item.get("timeStamp")
        ]
        cpu_usage = [_safe_float(item.get("average", 0.0)) for item in data_points]
        return {"labels": labels, "values": cpu_usage}
    except Exception:
        return _empty_series()


async def fetch_azure_data(resource_id: str = AZURE_VM_RESOURCE_ID) -> dict[str, list[float] | list[str]]:
    return await asyncio.to_thread(get_azure_metrics, resource_id)


async def fetch_cloud_data() -> dict[str, list[float] | list[str]]:
    return await fetch_azure_data()


async def build_dashboard_forecast() -> dict[str, Any]:
    stocks, crypto, sentiment, cloud = await asyncio.gather(
        fetch_stock_data(),
        fetch_crypto_data(),
        fetch_sentiment_data(),
        fetch_cloud_data(),
    )

    return {
        "stocks": stocks,
        "crypto": crypto,
        "sentiment": sentiment,
        "cloud": cloud,
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