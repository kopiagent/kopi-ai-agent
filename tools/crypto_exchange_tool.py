#!/usr/bin/env python3
"""
Crypto Exchange Trading Tool (sandbox-first)
============================================

``crypto_exchange`` — quotes, orders, balances and positions on Binance and
OKX through ccxt's unified API. One tool covers every supported exchange:
ccxt normalizes symbols, order shapes and testnet plumbing, so adding an
exchange later is one entry in :data:`_EXCHANGES`, not a new tool.

Design notes
------------
- **Sandbox by default, mainnet by double opt-in.** Every client is created
  with ``set_sandbox_mode(True)`` unless BOTH of these hold: the operator has
  exported ``KOPI_EXCHANGE_ALLOW_MAINNET=true`` AND the call passes
  ``live: true``. The refusal happens in code before a client is even
  constructed — it does not depend on which keys happen to be configured.
  ccxt makes switching environments a one-liner, which is exactly why the
  gate has to live here.
- **ccxt is lazy.** The package is ~4 MB and only traders need it; it is
  installed on first use via ``lazy_deps`` (feature ``trading.ccxt``,
  mirrored by the ``trading`` extra in pyproject.toml).
- **Trimmed output.** ccxt attaches the raw exchange payload under ``info``
  on every ticker/order/position — hundreds of duplicated fields per call.
  Handlers return a fixed field subset so a portfolio snapshot doesn't eat
  the context window.
- **US equities are NOT here.** Alpaca is served by its official MCP server
  (``kopi mcp install alpaca``), which is first-party maintained; wrapping
  its SDK in this tool would just be a worse copy.

Credentials come from the environment (``~/.kopi/.env`` is the usual home):
Binance testnet keys from https://testnet.binance.vision, OKX demo-trading
keys from the OKX web console (Trade → Demo trading → API).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# The operator-level mainnet switch. Without it, live=true is refused in code.
_MAINNET_ENV = "KOPI_EXCHANGE_ALLOW_MAINNET"

# ccxt credential field → environment variable, per exchange. OKX API keys
# additionally require the passphrase chosen at key creation ("password" in
# ccxt terms).
_EXCHANGES: Dict[str, Dict[str, str]] = {
    "binance": {
        "apiKey": "BINANCE_API_KEY",
        "secret": "BINANCE_API_SECRET",
    },
    "okx": {
        "apiKey": "OKX_API_KEY",
        "secret": "OKX_API_SECRET",
        "password": "OKX_API_PASSWORD",
    },
}

# Operations that sign requests with the account keys. `ticker` is public
# market data and works without credentials.
_PRIVATE_OPERATIONS = frozenset(
    {"balance", "create_order", "cancel_order", "open_orders", "order_status", "positions"}
)

_MARKET_TYPES = ("spot", "swap", "future")

_TICKER_FIELDS = (
    "symbol", "timestamp", "datetime", "last", "bid", "ask", "high", "low",
    "open", "close", "previousClose", "change", "percentage", "baseVolume",
    "quoteVolume",
)
_ORDER_FIELDS = (
    "id", "clientOrderId", "symbol", "type", "side", "price", "average",
    "amount", "filled", "remaining", "status", "timestamp", "datetime", "fee",
)
_POSITION_FIELDS = (
    "symbol", "side", "contracts", "contractSize", "entryPrice", "markPrice",
    "notional", "leverage", "unrealizedPnl", "percentage", "liquidationPrice",
    "marginMode", "timestamp", "datetime",
)


def _import_ccxt() -> Any:
    """Import ccxt, lazily installing it on first use (see fal_common.py)."""
    try:
        from tools.lazy_deps import ensure as _lazy_ensure

        _lazy_ensure("trading.ccxt", prompt=False)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — lazy_deps surfaces install hints
        raise ImportError(str(exc))
    import ccxt  # type: ignore  # noqa: WPS433 — intentionally lazy

    return ccxt


def check_crypto_exchange_requirements() -> bool:
    """The tool is always offerable; ccxt installs lazily and credential
    problems produce actionable per-call errors."""
    return True


def _mainnet_enabled() -> bool:
    return os.environ.get(_MAINNET_ENV, "").strip().lower() in ("1", "true", "yes")


def _credentials(exchange_id: str) -> Tuple[Dict[str, str], List[str]]:
    """Return (ccxt credential kwargs, missing env var names)."""
    creds: Dict[str, str] = {}
    missing: List[str] = []
    for ccxt_field, env_name in _EXCHANGES[exchange_id].items():
        value = os.environ.get(env_name, "").strip()
        if value:
            creds[ccxt_field] = value
        else:
            missing.append(env_name)
    return creds, missing


def _build_client(exchange_id: str, creds: Dict[str, str], live: bool, market_type: str) -> Any:
    ccxt = _import_ccxt()
    exchange_class = getattr(ccxt, exchange_id)
    client = exchange_class(
        {
            "enableRateLimit": True,
            "options": {"defaultType": market_type},
            **creds,
        }
    )
    if not live:
        client.set_sandbox_mode(True)
    return client


def _trim(record: Any, fields: Tuple[str, ...]) -> Dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    return {k: record[k] for k in fields if record.get(k) is not None}


def _require_str(args: Dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required for this operation.")
    return value.strip()


# ─── Operation handlers ──────────────────────────────────────────────────────
# Each returns a dict of payload fields; the dispatcher wraps it in
# tool_result together with the operation/exchange/environment tags.


def _op_ticker(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = _require_str(args, "symbol")
    return {"ticker": _trim(client.fetch_ticker(symbol), _TICKER_FIELDS)}


def _op_balance(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    balance = client.fetch_balance()
    totals = balance.get("total") or {}
    free = balance.get("free") or {}
    used = balance.get("used") or {}
    nonzero = {
        currency: {
            "free": free.get(currency),
            "used": used.get(currency),
            "total": total,
        }
        for currency, total in totals.items()
        if total
    }
    return {"balances": nonzero}


def _op_create_order(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = _require_str(args, "symbol")
    side = _require_str(args, "side").lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"'side' must be buy or sell, got {side!r}.")
    order_type = _require_str(args, "order_type").lower()
    if order_type not in ("market", "limit"):
        raise ValueError(f"'order_type' must be market or limit, got {order_type!r}.")
    amount = args.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' must be a positive number (base-currency units).")
    price = args.get("price")
    if order_type == "limit":
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError("'price' is required for limit orders.")
    else:
        price = None
    order = client.create_order(symbol, order_type, side, amount, price)
    return {"order": _trim(order, _ORDER_FIELDS)}


def _op_open_orders(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol") or None
    orders = client.fetch_open_orders(symbol)
    return {
        "open_orders": [_trim(o, _ORDER_FIELDS) for o in orders],
        "count": len(orders),
    }


def _op_order_status(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    order_id = _require_str(args, "order_id")
    symbol = _require_str(args, "symbol")
    return {"order": _trim(client.fetch_order(order_id, symbol), _ORDER_FIELDS)}


def _op_cancel_order(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    order_id = _require_str(args, "order_id")
    symbol = _require_str(args, "symbol")
    result = client.cancel_order(order_id, symbol)
    return {"order": _trim(result, _ORDER_FIELDS), "canceled": True}


def _op_positions(client: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol") or None
    positions = client.fetch_positions([symbol] if symbol else None)
    open_positions = [
        _trim(p, _POSITION_FIELDS) for p in positions if (p or {}).get("contracts")
    ]
    return {"positions": open_positions, "count": len(open_positions)}


_OPERATIONS = {
    "ticker": _op_ticker,
    "balance": _op_balance,
    "create_order": _op_create_order,
    "open_orders": _op_open_orders,
    "order_status": _op_order_status,
    "cancel_order": _op_cancel_order,
    "positions": _op_positions,
}


CRYPTO_EXCHANGE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": sorted(_OPERATIONS),
            "description": (
                "ticker: price snapshot for one symbol (public, no keys needed). "
                "balance: non-zero account balances. create_order: place a "
                "market or limit order. open_orders: list resting orders. "
                "order_status: look up one order. cancel_order: cancel one "
                "order. positions: open derivative positions (needs "
                "market_type swap or future; spot has no positions)."
            ),
        },
        "exchange": {
            "type": "string",
            "enum": sorted(_EXCHANGES),
            "description": (
                "Which exchange to talk to. Credentials come from the "
                "environment: BINANCE_API_KEY/BINANCE_API_SECRET, or "
                "OKX_API_KEY/OKX_API_SECRET/OKX_API_PASSWORD."
            ),
        },
        "symbol": {
            "type": "string",
            "description": (
                "Unified ccxt market symbol, e.g. 'BTC/USDT' (spot) or "
                "'BTC/USDT:USDT' (USDT-margined swap)."
            ),
        },
        "side": {"type": "string", "enum": ["buy", "sell"], "description": "create_order only."},
        "order_type": {
            "type": "string",
            "enum": ["market", "limit"],
            "description": "create_order only — limit orders also need `price`.",
        },
        "amount": {
            "type": "number",
            "description": "create_order only — order size in base-currency units.",
        },
        "price": {
            "type": "number",
            "description": "create_order only — limit price (required for limit orders).",
        },
        "order_id": {
            "type": "string",
            "description": "order_status / cancel_order — the exchange order id.",
        },
        "market_type": {
            "type": "string",
            "enum": sorted(_MARKET_TYPES),
            "description": "Market segment to trade (default spot). positions needs swap/future.",
        },
        "live": {
            "type": "boolean",
            "description": (
                "Target the REAL exchange instead of the sandbox/testnet. "
                "Refused outright unless the operator has exported "
                "KOPI_EXCHANGE_ALLOW_MAINNET=true. Default false = sandbox."
            ),
        },
    },
    "required": ["operation", "exchange"],
    "additionalProperties": False,
}


def _handle_crypto_exchange(args: Dict[str, Any], **_kwargs: Any) -> str:
    operation = args.get("operation")
    handler = _OPERATIONS.get(operation if isinstance(operation, str) else "")
    if handler is None:
        return tool_error(
            f"unknown operation {operation!r}; expected one of {sorted(_OPERATIONS)}."
        )

    exchange_id = args.get("exchange")
    if exchange_id not in _EXCHANGES:
        return tool_error(
            f"unknown exchange {exchange_id!r}; expected one of {sorted(_EXCHANGES)}."
        )

    # The mainnet gate runs before anything else — before credentials are
    # read and before a client exists. live=true without the operator env
    # switch is a hard refusal, not a fallback to sandbox, so the model
    # can't "succeed" while silently targeting a different environment
    # than it asked for.
    live = bool(args.get("live"))
    if live and not _mainnet_enabled():
        return tool_error(
            "refused: live=true targets the REAL exchange with real money, but "
            f"the operator switch is off. Export {_MAINNET_ENV}=true to enable "
            "mainnet trading; until then every call runs on the exchange "
            "sandbox/testnet (omit `live`)."
        )

    market_type = args.get("market_type") or "spot"
    if market_type not in _MARKET_TYPES:
        return tool_error(
            f"unknown market_type {market_type!r}; expected one of {sorted(_MARKET_TYPES)}."
        )

    creds, missing = _credentials(exchange_id)
    if operation in _PRIVATE_OPERATIONS and missing:
        return tool_error(
            f"missing {exchange_id} credentials: set {', '.join(missing)} in the "
            "environment (~/.kopi/.env). Sandbox keys: Binance testnet — "
            "https://testnet.binance.vision; OKX — web console → Trade → "
            "Demo trading → API."
        )

    environment = "MAINNET (live)" if live else "sandbox"
    try:
        client = _build_client(exchange_id, creds, live, market_type)
        payload = handler(client, args)
    except ImportError as exc:
        return tool_error(f"ccxt is unavailable: {exc}")
    except ValueError as exc:
        return tool_error(str(exc))
    except Exception as exc:  # ccxt raises per-exchange subclasses of BaseError
        logger.exception("crypto_exchange %s failed on %s", operation, exchange_id)
        return tool_error(
            f"crypto_exchange {operation} failed on {exchange_id} ({environment}): {exc}"
        )
    return tool_result(
        operation=operation, exchange=exchange_id, environment=environment, **payload
    )


registry.register(
    name="crypto_exchange",
    toolset="trading",
    schema=CRYPTO_EXCHANGE_SCHEMA,
    handler=_handle_crypto_exchange,
    check_fn=check_crypto_exchange_requirements,
    requires_env=[],
    is_async=False,
    emoji="💱",
)
