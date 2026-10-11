"""ccusage collector — an independent, machine-wide daily cost total to reconcile against.

Pathly's own cost rows are produced by two parsers it owns (Strategy A token counting,
Strategy B pricing). ``ccusage`` (github.com/ryoppippi/ccusage) reads the CLIs' on-disk
transcripts and prices them from its own maintained rate table, so it is an INDEPENDENT
measurement of the same spend: if Pathly ever claims more than ccusage saw for the whole
machine, a parser or a rate in ``db/pricing.py`` is wrong. See ``runner/cost_reconcile.py``.

Optional and external, like the code-intel backends: not a pip/npm dep. Resolved via
``PATHLY_CCUSAGE_BIN`` or ``ccusage`` on PATH; absent → every caller degrades to ``None``.
Never ``npx`` — that is a registry lookup on every call. ``--offline`` keeps ccusage from
fetching prices over the network.

Shape notes (measured against ccusage 20.x by the daycap project): ``ccusage daily`` ALREADY
includes codex, so it is spawned once (spawning ``ccusage codex daily`` too double-counts);
the per-tool split comes from ``modelBreakdowns[]``; the date key is ``period`` (``date`` on
older versions) and the cost key drifts between ``cost``/``costUSD``/``totalCost``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
from datetime import date
from typing import Any

from ..db.pricing import infer_provider

logger = logging.getLogger("pathly.telemetry")

DEFAULT_TIMEOUT_S = 120.0  # ccusage reads the whole transcript corpus on every call


def resolve_ccusage() -> str | None:
    """Path to a ccusage binary, or None. ``PATHLY_CCUSAGE_BIN`` wins over PATH."""
    explicit = (os.environ.get("PATHLY_CCUSAGE_BIN") or "").strip()
    if explicit:
        return explicit if os.path.exists(explicit) else None
    return shutil.which("ccusage")


def tool_for_model(model: str) -> str:
    """Bucket a ccusage model name into Pathly's adapter vocabulary (``claude``/``codex``/…),
    via the same prefix table Pathly prices with. An unknown family keeps its own name, so it
    is reported rather than silently dropped."""
    slug = infer_provider(model)
    return slug if slug != "unknown" else (model or "unknown").strip().lower()


def _cost(d: dict[str, Any]) -> float | None:
    for key in ("cost", "costUSD", "totalCost"):
        v = d.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def parse_ccusage_daily(raw: Any) -> dict[str, dict[str, float]]:
    """Parse ``ccusage daily --json`` → ``{YYYY-MM-DD: {tool: usd}}``.

    Alias-tolerant (see module docstring). A row without ``modelBreakdowns`` is attributed
    whole to ``"unattributed"`` — a correct total under a coarse label beats a dropped day.
    Raises ``ValueError`` on an unrecognised top-level shape (keys only, never values).
    """
    rows = raw.get("daily") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        keys = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        raise ValueError(f"ccusage: no daily[] array (top-level: {keys})")
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = row.get("period") or row.get("date")
        if not isinstance(day, str) or len(day) < 10:
            continue
        bucket = out.setdefault(day[:10], {})
        breakdowns = row.get("modelBreakdowns")
        if isinstance(breakdowns, list) and breakdowns:
            for b in breakdowns:
                if isinstance(b, dict) and isinstance(b.get("modelName"), str):
                    tool = tool_for_model(b["modelName"])
                    bucket[tool] = bucket.get(tool, 0.0) + (_cost(b) or 0.0)
            continue
        bucket["unattributed"] = bucket.get("unattributed", 0.0) + (_cost(row) or 0.0)
    return out


def ccusage_daily(
    since: date, until: date, timeout: float = DEFAULT_TIMEOUT_S
) -> dict[str, dict[str, float]] | None:
    """Run ``ccusage daily`` for the inclusive local-date range. ``None`` when ccusage is
    absent, fails, times out or emits an unrecognised shape — never raises."""
    binary = resolve_ccusage()
    if not binary:
        return None
    argv = [
        binary,
        "daily",
        "--json",
        "--offline",
        "--since",
        since.strftime("%Y%m%d"),
        "--until",
        until.strftime("%Y%m%d"),
    ]
    try:
        proc = subprocess.run(  # nosec B603 - fixed argv, resolved binary, no shell
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
        if proc.returncode != 0:
            logger.warning(
                "ccusage exited %s: %s", proc.returncode, (proc.stderr or "")[:200]
            )
            return None
        return parse_ccusage_daily(json.loads(proc.stdout))
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        logger.warning("ccusage daily unavailable: %s", exc)
        return None
