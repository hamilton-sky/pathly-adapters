"""HQ copilot settings — hq.* keys (hq-copilot ticket 05).

HQ-ONLY: the fleet copilot's default model, context-packet token budget,
packet section order, and which operator actions HQ may use
(``hq.actions.available``, local-operator). Nothing outside HQ reads these keys.

Split out of ``app_settings.py`` (400-line ratchet) and re-exported from it,
so ``from ...app_settings import get_hq_budget_tokens`` keeps working — the
same split+re-export pattern as ``comms_hydrate``.
"""

from __future__ import annotations

import json
import sqlite3

from .app_settings import get_setting, set_setting

_HQ_DEFAULT_MODEL_KEY = "hq.default_model"
_HQ_BUDGET_KEY = "hq.context_budget_tokens"
_HQ_PACKET_ORDER_KEY = "hq.packet_order"
_HQ_ACTIONS_AVAILABLE_KEY = "hq.actions.available"

# Ticket 01 settlements: default model qwen3-8b (24 GB machine; phi-4-mini is
# the zero-friction fallback), budget 6000 tokens, order attention.
HQ_DEFAULT_MODEL = "qwen3-8b"
HQ_DEFAULT_BUDGET_TOKENS = 6000
HQ_DEFAULT_PACKET_ORDER = "attention"


def get_hq_default_model(conn: sqlite3.Connection) -> str:
    """HQ-only: the local model id answering HQ chats."""
    try:
        raw = get_setting(conn, _HQ_DEFAULT_MODEL_KEY, HQ_DEFAULT_MODEL)
    except sqlite3.OperationalError:
        return HQ_DEFAULT_MODEL
    return (raw or "").strip() or HQ_DEFAULT_MODEL


def get_hq_budget_tokens(conn: sqlite3.Connection) -> int:
    """HQ-only: the context-packet token budget. Garbage falls back to the
    default rather than breaking assembly."""
    try:
        raw = get_setting(conn, _HQ_BUDGET_KEY, None)
    except sqlite3.OperationalError:
        return HQ_DEFAULT_BUDGET_TOKENS
    if raw is None:
        return HQ_DEFAULT_BUDGET_TOKENS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return HQ_DEFAULT_BUDGET_TOKENS
    return value if value > 0 else HQ_DEFAULT_BUDGET_TOKENS


def get_hq_packet_order(conn: sqlite3.Connection) -> str:
    """HQ-only: 'attention' (default) or 'progress'. Anything else falls back
    to the default rather than breaking assembly."""
    try:
        raw = get_setting(conn, _HQ_PACKET_ORDER_KEY, HQ_DEFAULT_PACKET_ORDER)
    except sqlite3.OperationalError:
        return HQ_DEFAULT_PACKET_ORDER
    return raw if raw in ("attention", "progress") else HQ_DEFAULT_PACKET_ORDER


def set_hq_packet_order(conn: sqlite3.Connection, order: str) -> None:
    """Set the HQ packet order. Raises ValueError on anything but
    'attention' | 'progress'."""
    if order not in ("attention", "progress"):
        raise ValueError("order must be 'attention' or 'progress'")
    set_setting(conn, _HQ_PACKET_ORDER_KEY, order)


def get_hq_available_actions(conn: sqlite3.Connection) -> list[str] | None:
    """HQ-only: the operator action names Settings lets HQ use, or None when
    never set (or unreadable) — the caller then applies the catalog default
    (hq_actions.default_available). Names are not checked against the catalog
    here; db/ imports nothing above it."""
    try:
        raw = get_setting(conn, _HQ_ACTIONS_AVAILABLE_KEY, None)
    except sqlite3.OperationalError:
        return None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return [n for n in data if isinstance(n, str)]


def set_hq_available_actions(conn: sqlite3.Connection, names: list[str]) -> None:
    """Store the operator actions HQ may use (already catalog-checked)."""
    set_setting(conn, _HQ_ACTIONS_AVAILABLE_KEY, json.dumps(list(names)))
