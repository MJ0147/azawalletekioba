"""The dashboard's market data: real numbers from named sources, or an honest blank.

No test here touches the network. The providers are stubbed; what is checked is the parsing, the
provider chain, the trend maths, and above all that a failure never turns into a made-up price.
"""

import asyncio
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent


# ── The trend line ──────────────────────────────────────────────────────────


def test_trend_continues_a_straight_line_exactly():
    projected, fit = agent._trend([10.0, 11.0, 12.0, 13.0])
    assert projected == [14.0, 15.0, 16.0]
    assert fit == 1.0  # a perfect line through perfectly linear closes


def test_trend_reports_a_weak_fit_for_a_noisy_series():
    _, fit = agent._trend([10.0, 14.0, 9.0, 15.0, 8.0])
    assert fit < 0.5


def test_trend_holds_a_flat_series_flat():
    projected, fit = agent._trend([100.0, 100.0, 100.0])
    assert projected == [100.0, 100.0, 100.0]
    assert fit == 0.0


def test_trend_never_projects_a_negative_price():
    projected, _ = agent._trend([10.0, 7.0, 4.0, 1.0])
    assert all(value >= 0 for value in projected)


def test_trend_of_nothing_is_nothing():
    assert agent._trend([]) == ([], 0.0)


# ── Yahoo Finance ───────────────────────────────────────────────────────────


def _yahoo_payload(*, closes, timestamps, quote_price=None, quote_time=None):
    meta = {"currency": "USD", "fullExchangeName": "NasdaqGS", "symbol": "AAPL"}
    if quote_price is not None:
        meta["regularMarketPrice"] = quote_price
        meta["regularMarketTime"] = quote_time
    return {"chart": {"result": [{
        "meta": meta,
        "timestamp": list(timestamps),
        "indicators": {"quote": [{"close": list(closes)}]},
    }]}}


HOUR = 3600
BASE_TIME = 1789646400  # a round hour, UTC


def test_yahoo_parse_drops_buckets_that_never_traded():
    payload = _yahoo_payload(
        closes=[100.0, None, 102.0],
        timestamps=[BASE_TIME, BASE_TIME + HOUR, BASE_TIME + 2 * HOUR],
    )
    series = agent._parse_yahoo_chart(payload, "AAPL")
    assert series["actual"] == [100.0, 102.0]
    assert series["status"] == "ok"
    assert series["source"] == "Yahoo Finance"
    assert series["currency"] == "USD"


def test_yahoo_parse_replaces_the_last_bar_with_a_quote_from_inside_it():
    """A quote a minute after the last bar is that bar, printed again — not a new point."""
    payload = _yahoo_payload(
        closes=[100.0, 102.0],
        timestamps=[BASE_TIME, BASE_TIME + HOUR],
        quote_price=103.5,
        quote_time=BASE_TIME + HOUR + 60,
    )
    series = agent._parse_yahoo_chart(payload, "AAPL")
    assert series["actual"] == [100.0, 103.5]
    assert series["latest"] == 103.5
    assert series["as_of"] == datetime.fromtimestamp(BASE_TIME + HOUR + 60, tz=timezone.utc).isoformat()


def test_yahoo_parse_appends_a_quote_from_a_later_bar():
    payload = _yahoo_payload(
        closes=[100.0, 102.0],
        timestamps=[BASE_TIME, BASE_TIME + HOUR],
        quote_price=104.0,
        quote_time=BASE_TIME + 2 * HOUR + 30,
    )
    series = agent._parse_yahoo_chart(payload, "AAPL")
    assert series["actual"] == [100.0, 102.0, 104.0]


def test_yahoo_parse_labels_the_extrapolated_points_one_interval_apart():
    payload = _yahoo_payload(
        closes=[100.0, 101.0, 102.0],
        timestamps=[BASE_TIME, BASE_TIME + HOUR, BASE_TIME + 2 * HOUR],
    )
    series = agent._parse_yahoo_chart(payload, "AAPL")
    assert len(series["predicted"]) == len(series["predicted_labels"]) == 3
    assert series["predicted_labels"][0] == agent._label(
        datetime.fromtimestamp(BASE_TIME + 3 * HOUR, tz=timezone.utc)
    )


def test_yahoo_parse_refuses_an_empty_result():
    with pytest.raises(ValueError):
        agent._parse_yahoo_chart({"chart": {"result": []}}, "AAPL")


# ── Trading pairs ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "symbol, expected",
    [("BTCUSDT", ("BTC", "USDT")), ("ETHUSD", ("ETH", "USD")), ("TONUSDT", ("TON", "USDT")), ("BTC", ("BTC", "USDT"))],
)
def test_pairs_split_into_base_and_quote(symbol, expected):
    assert agent._split_pair(symbol) == expected


def test_stablecoin_quotes_are_reported_as_dollars():
    assert agent._fiat_quote("USDT") == "USD"
    assert agent._fiat_quote("EUR") == "EUR"


# ── The provider chain ──────────────────────────────────────────────────────


def _series(source, price):
    moment = datetime.fromtimestamp(BASE_TIME, tz=timezone.utc)
    return agent._series([moment], [price], source=source, symbol="BTCUSDT")


def test_the_next_exchange_answers_when_the_first_is_blocked(monkeypatch):
    async def blocked(*args):
        raise RuntimeError("HTTP 451")

    async def coinbase(*args):
        return _series("Coinbase", 70000.0)

    monkeypatch.setattr(agent, "_binance", blocked)
    monkeypatch.setattr(agent, "_coinbase", coinbase)

    series = asyncio.run(agent.fetch_crypto_data("BTCUSDT"))
    assert series["source"] == "Coinbase"
    assert series["latest"] == 70000.0


def test_every_exchange_failing_yields_no_prices_and_says_who_was_tried(monkeypatch):
    async def blocked(*args):
        raise RuntimeError("nope")

    for name in ("_binance", "_coinbase", "_kraken", "_coingecko"):
        monkeypatch.setattr(agent, name, blocked)

    series = asyncio.run(agent.fetch_crypto_data("BTCUSDT"))
    assert series["status"] == "unavailable"
    assert series["actual"] == [] and series["predicted"] == []
    assert "Binance" in series["error"] and "CoinGecko" in series["error"]


def test_a_provider_that_answers_with_nothing_is_passed_over(monkeypatch):
    async def empty(*args):
        return agent.empty_series("no candles")

    async def kraken(*args):
        return _series("Kraken", 69000.0)

    monkeypatch.setattr(agent, "_binance", empty)
    monkeypatch.setattr(agent, "_coinbase", empty)
    monkeypatch.setattr(agent, "_kraken", kraken)

    assert (asyncio.run(agent.fetch_crypto_data("BTCUSDT")))["source"] == "Kraken"


# ── The whole payload ───────────────────────────────────────────────────────


def test_a_panel_that_fails_never_borrows_numbers(monkeypatch):
    async def broken():
        raise RuntimeError("provider down")

    async def crypto():
        return _series("Binance", 76000.0)

    monkeypatch.setattr(agent, "fetch_stock_data", broken)
    monkeypatch.setattr(agent, "fetch_crypto_data", crypto)
    monkeypatch.setattr(agent, "fetch_sentiment_data", broken)
    monkeypatch.setattr(agent, "fetch_cloud_data", broken)

    payload = asyncio.run(agent.build_dashboard_forecast())
    assert payload["crypto"]["latest"] == 76000.0
    assert payload["stocks"]["status"] == "unavailable"
    assert payload["stocks"]["actual"] == []
    assert payload["sentiment"]["values"] == []
    assert payload["status"] == "ok"  # one live panel is still a live dashboard


def test_a_dashboard_with_nothing_live_reports_itself_unavailable(monkeypatch):
    async def broken():
        raise RuntimeError("provider down")

    for name in ("fetch_stock_data", "fetch_crypto_data", "fetch_sentiment_data", "fetch_cloud_data"):
        monkeypatch.setattr(agent, name, broken)

    payload = asyncio.run(agent.build_dashboard_forecast())
    assert payload["status"] == "unavailable"
    assert not any(payload[key]["labels"] for key in ("stocks", "crypto", "sentiment", "cloud"))


def test_live_data_is_cached_but_an_outage_is_retried(monkeypatch):
    calls = []

    async def build():
        calls.append(1)
        return {"status": "unavailable", "stocks": agent.empty_series()}

    agent.clear_cache()
    monkeypatch.setattr(agent, "build_dashboard_forecast", build)
    asyncio.run(agent.get_dashboard_forecast())
    asyncio.run(agent.get_dashboard_forecast())
    assert len(calls) == 2, "an unavailable dashboard must not be pinned in the cache"

    async def live():
        calls.append(1)
        return {"status": "ok", "stocks": _series("Binance", 1.0)}

    monkeypatch.setattr(agent, "build_dashboard_forecast", live)
    asyncio.run(agent.get_dashboard_forecast())
    before = len(calls)
    asyncio.run(agent.get_dashboard_forecast())
    assert len(calls) == before, "a live dashboard is served from the cache"
    agent.clear_cache()


def test_the_module_ships_no_stand_in_prices():
    """The old dashboard fell back to invented closes ($145 AAPL, $32,000 BTC). Never again."""
    assert not hasattr(agent, "DEFAULT_FORECAST_DATA")
    blank = agent.unavailable_forecast("providers unreachable")
    assert blank["stocks"]["actual"] == [] and blank["crypto"]["actual"] == []
    assert blank["status"] == "unavailable"


# ── What the site says about the market ─────────────────────────────────────


@pytest.fixture(scope="module")
def frontend():
    spec = importlib.util.spec_from_file_location(
        "ekioba_frontend_app_market", Path(__file__).resolve().parents[1] / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_market_reply_quotes_the_real_price_and_names_the_venue(frontend):
    reply = frontend._market_snapshot({
        "stocks": _series("Yahoo Finance", 332.41),
        "crypto": _series("Binance", 76947.03),
        "sentiment": {"status": "ok", "values": [50.0], "classification": "Neutral"},
    })
    assert "332.41" in reply and "Yahoo Finance" in reply
    assert "76,947.03" in reply and "Binance" in reply
    assert "50 out of 100 (Neutral)" in reply
    assert "not a prediction of the market" in reply


def test_the_market_reply_refuses_to_quote_a_price_it_could_not_fetch(frontend):
    reply = frontend._market_snapshot(agent.unavailable_forecast("providers unreachable"))
    assert "can't reach the market data providers" in reply
    assert not re.search(r"\d+\.\d\d", reply), "no figure may appear when nothing was fetched"


def test_the_dashboard_endpoint_reports_an_outage_rather_than_inventing_one(frontend, monkeypatch):
    async def broken():
        raise RuntimeError("all providers down")

    monkeypatch.setattr(frontend, "get_dashboard_forecast", broken)
    payload = TestClient(frontend.app).get("/api/dashboard/forecast").json()

    assert payload["status"] == "unavailable"
    for panel in ("stocks", "crypto"):
        assert payload[panel]["actual"] == []
        assert payload[panel]["status"] == "unavailable"
