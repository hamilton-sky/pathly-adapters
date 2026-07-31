"""Live-status + capability overlay for the unified run read-model (unified-control-plane P0).

supervisor/ layer — imports only sibling ``supervisor`` modules (layer-safe). A THIN display
overlay on top of the DB read-model: DB-on-mount is the invariant (SPEC risk 5), so this only
upgrades a persisted ``'running'`` row to the live registry status and attaches a display-only
capability hint. It is never the source of runs.
"""

from __future__ import annotations

# Per-kind capability hints (display-only in P0 — the Pipelines pane is read-only; the real
# controls arrive in P3). Included now so the read-model shape is stable for later phases.
_CAPS: dict[str, list[str]] = {
    "flow": ["abort"],
    "single": ["abort"],
    "loop": ["abort"],
    "decompose": ["abort"],
}


def overlay_live_status(runs: list[dict]) -> list[dict]:
    """Upgrade any persisted ``'running'`` row to the live registry status and attach a
    per-kind ``capabilities`` list. Mutates + returns the same list (the caller passes a
    fresh read-model result).

    The registry is keyed by TOPIC; its ``RunnerState`` values carry ``run_id`` + ``status``,
    so index them by ``run_id`` to match the read-model rows. Layer-safe: ``supervisor`` →
    ``registry`` only.
    """
    from .registry import _lock, _registry

    with _lock:
        live = {
            s.run_id: s.status
            for s in _registry.values()
            if getattr(s, "run_id", None)
        }
    for r in runs:
        if r.get("status") == "running" and r.get("run_id") in live:
            r["status"] = live[r["run_id"]]
        r["capabilities"] = _CAPS.get(r.get("kind") or "", [])
    return runs
