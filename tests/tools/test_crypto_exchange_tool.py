"""The whole point of `crypto_exchange` is the sandbox-first gate: ccxt makes
mainnet a one-liner, so the tool must be the thing that refuses it. These
tests pin the gate (sandbox forced by default, live=true refused without the
operator env switch, honored with it) plus the ccxt passthrough shapes,
using a fake ccxt so no network or real package is involved.
"""

import json
from types import SimpleNamespace

import pytest

from tools import crypto_exchange_tool
from tools.crypto_exchange_tool import _MAINNET_ENV, _handle_crypto_exchange


class FakeExchange:
    """Records construction and calls; returns ccxt-shaped payloads."""

    instances = []

    def __init__(self, config):
        self.config = config
        self.sandbox_calls = []
        self.created_orders = []
        FakeExchange.instances.append(self)

    def set_sandbox_mode(self, flag):
        self.sandbox_calls.append(flag)

    def fetch_ticker(self, symbol):
        return {
            "symbol": symbol,
            "last": 50000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "info": {"raw": "exchange payload that must not leak"},
        }

    def create_order(self, symbol, order_type, side, amount, price=None):
        self.created_orders.append((symbol, order_type, side, amount, price))
        return {
            "id": "order-1",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open",
            "info": {"raw": True},
        }

    def fetch_balance(self):
        return {
            "free": {"USDT": 950.0, "BTC": 0.0},
            "used": {"USDT": 50.0, "BTC": 0.0},
            "total": {"USDT": 1000.0, "BTC": 0.0},
            "info": {},
        }

    def fetch_open_orders(self, symbol=None):
        return [{"id": "order-1", "symbol": symbol or "BTC/USDT", "status": "open"}]

    def fetch_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol, "status": "closed", "filled": 1.0}

    def cancel_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol, "status": "canceled"}

    def fetch_positions(self, symbols=None):
        return [
            {"symbol": "BTC/USDT:USDT", "contracts": 2, "side": "long", "entryPrice": 50000.0},
            {"symbol": "ETH/USDT:USDT", "contracts": 0, "side": None},
        ]


@pytest.fixture
def fake_ccxt(monkeypatch):
    """Route _import_ccxt to a fake module; isolate env and instance log."""
    FakeExchange.instances = []
    fake = SimpleNamespace(binance=FakeExchange, okx=FakeExchange)
    monkeypatch.setattr(crypto_exchange_tool, "_import_ccxt", lambda: fake)
    monkeypatch.delenv(_MAINNET_ENV, raising=False)
    for var in (
        "BINANCE_API_KEY", "BINANCE_API_SECRET",
        "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)
    return fake


def _call(**args):
    return json.loads(_handle_crypto_exchange(args))


def _with_binance_keys(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "test-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "test-secret")


def test_sandbox_mode_is_forced_by_default(fake_ccxt):
    result = _call(operation="ticker", exchange="binance", symbol="BTC/USDT")
    assert result["environment"] == "sandbox"
    assert FakeExchange.instances[0].sandbox_calls == [True]


def test_live_is_refused_without_operator_switch(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    result = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="buy", order_type="market", amount=0.1, live=True,
    )
    assert _MAINNET_ENV in result["error"]
    # Refused before a client was even constructed — nothing to leak through.
    assert FakeExchange.instances == []


def test_live_honored_with_operator_switch(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    monkeypatch.setenv(_MAINNET_ENV, "true")
    result = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="buy", order_type="limit", amount=0.1, price=48000.0, live=True,
    )
    assert result["environment"] == "MAINNET (live)"
    client = FakeExchange.instances[0]
    assert client.sandbox_calls == []  # live client never enters sandbox mode
    assert client.created_orders == [("BTC/USDT", "limit", "buy", 0.1, 48000.0)]


def test_operator_switch_alone_does_not_go_live(fake_ccxt, monkeypatch):
    """Double opt-in: the env switch without live=true stays in sandbox."""
    _with_binance_keys(monkeypatch)
    monkeypatch.setenv(_MAINNET_ENV, "true")
    result = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="sell", order_type="market", amount=0.5,
    )
    assert result["environment"] == "sandbox"
    assert FakeExchange.instances[0].sandbox_calls == [True]


def test_sandbox_order_passthrough(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    result = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="buy", order_type="market", amount=0.25,
    )
    assert result["order"]["id"] == "order-1"
    # Market orders never forward a price.
    assert FakeExchange.instances[0].created_orders == [
        ("BTC/USDT", "market", "buy", 0.25, None)
    ]


def test_private_operation_names_missing_env_vars(fake_ccxt):
    result = _call(operation="balance", exchange="okx")
    for var in ("OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSWORD"):
        assert var in result["error"]
    assert FakeExchange.instances == []


def test_public_ticker_needs_no_credentials(fake_ccxt):
    result = _call(operation="ticker", exchange="binance", symbol="ETH/USDT")
    assert result["ticker"]["last"] == 50000.0


def test_raw_exchange_payload_is_stripped(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    ticker = _call(operation="ticker", exchange="binance", symbol="BTC/USDT")
    order = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="buy", order_type="market", amount=0.1,
    )
    assert "info" not in ticker["ticker"]
    assert "info" not in order["order"]


def test_limit_order_requires_price(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    result = _call(
        operation="create_order", exchange="binance", symbol="BTC/USDT",
        side="buy", order_type="limit", amount=0.1,
    )
    assert "price" in result["error"]
    assert FakeExchange.instances[0].created_orders == []


def test_unknown_exchange_is_rejected(fake_ccxt):
    result = _call(operation="ticker", exchange="mtgox", symbol="BTC/USDT")
    assert "mtgox" in result["error"]
    assert "binance" in result["error"]


def test_balance_drops_zero_holdings(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    result = _call(operation="balance", exchange="binance")
    assert result["balances"] == {
        "USDT": {"free": 950.0, "used": 50.0, "total": 1000.0}
    }


def test_positions_drop_zero_contracts(fake_ccxt, monkeypatch):
    _with_binance_keys(monkeypatch)
    result = _call(operation="positions", exchange="binance", market_type="swap")
    assert result["count"] == 1
    assert result["positions"][0]["symbol"] == "BTC/USDT:USDT"
    # The client was built for the requested market segment.
    assert FakeExchange.instances[0].config["options"]["defaultType"] == "swap"
