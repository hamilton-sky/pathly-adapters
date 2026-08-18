"""Adapter capability flags — what a given CLI can do, as fragment gates.

A fragment may declare ``requires: can_spawn``; these helpers turn an adapter name (or a raw
dict) into the capability map that decides whether such a fragment survives composition.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml

from .compose_base import _KNOWN_ADAPTERS


def adapter_caps_for(adapter: str) -> dict:
    """Derive capability flags for an adapter from its ``_meta/*.yaml`` files.

    Currently derives ``can_spawn``: true when any agent meta declares a non-empty
    ``can_spawn`` list. Raises ``ValueError`` for an unknown adapter.
    """
    adapter = adapter or "claude"
    if adapter not in _KNOWN_ADAPTERS:
        raise ValueError(
            f"composition: unknown adapter {adapter!r}; known adapters: {sorted(_KNOWN_ADAPTERS)}"
        )
    meta_dir = files("pathly_data").joinpath(f"adapters/{adapter}/_meta")
    can_spawn = False
    try:
        for entry in meta_dir.iterdir():
            if not entry.name.endswith(".yaml"):
                continue
            try:
                meta = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if meta.get("can_spawn"):
                can_spawn = True
                break
    except (FileNotFoundError, OSError):
        pass
    return {"can_spawn": can_spawn}


def build_adapter_caps(
    adapter: str,
    *,
    goal_id: str = "",
    executor: str = "",
    kind: str = "",
) -> dict:
    """Build a capability dict by merging adapter hardware flags with goal context.

    Extends adapter_caps_for(adapter) with goal-level fields so fragments gated on
    requires:goal_id can be included when a goal run provides a goal_id.
    """
    caps = adapter_caps_for(adapter or "claude")
    caps["goal_id"] = goal_id or ""
    caps["executor"] = executor or ""
    caps["kind"] = kind or ""
    return caps


def _coerce_caps(adapter_caps: Any) -> dict:
    """Accept either a caps dict or an adapter-name string."""
    if adapter_caps is None:
        return {}
    if isinstance(adapter_caps, str):
        return adapter_caps_for(adapter_caps)
    if isinstance(adapter_caps, dict):
        return adapter_caps
    raise ValueError(
        f"composition: adapter_caps must be a dict or adapter-name str, got {type(adapter_caps).__name__}"
    )
