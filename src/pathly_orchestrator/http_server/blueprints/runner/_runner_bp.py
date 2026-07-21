"""Shared Blueprint object and helpers for the runner API routes."""

from flask import Blueprint

bp = Blueprint("runner", __name__)


def _topic_from_body(data: dict) -> str | None:
    topic = data.get("topic", "")
    return topic if isinstance(topic, str) and topic.strip() else None


# Flow-gate-preview (P2) — transient per-stage prompt override caps, so a pathological body
# can't blow the downstream argv/PowerShell path (DESIGN.md R5). Per-value cap first (a cheap
# char-slice bounding a single giant stage), total cap second — the AUTHORITATIVE guard —
# measured in the UTF-8 BYTES that actually reach the argv/PowerShell budget.
_MAX_STAGE_OVERRIDE_VALUE_CHARS = 64 * 1024
_MAX_STAGE_OVERRIDES_TOTAL_BYTES = 256 * 1024


def _validate_stage_overrides(raw, flow_name: str, project_root: str) -> dict:
    """Sanitize the transient per-stage prompt override map for /runner/start.

    dict[str, str] keyed by a DECLARED flow state; non-dict/empty input, non-string values,
    and blank strings are dropped. Keys not in the flow's own states are dropped too — unless
    the flow can't be loaded, in which case the state check is skipped (fail OPEN: an
    unmatched key just never applies at spawn, see fsm_ops.next_action). Values are truncated
    to the per-entry cap; entries stop being added once the total cap is reached. Malformed
    input of any shape degrades to {} (ignored → every stage composes normally) — a bad
    override must never 500 or block a run.
    """
    if not isinstance(raw, dict) or not raw:
        return {}

    states: set = set()
    try:
        from pathly_orchestrator.fsm_ops import _load_flow

        states = set((_load_flow(flow_name, project_root or None) or {}).get("states") or [])
    except Exception:
        states = set()

    out: dict[str, str] = {}
    total = 0
    for state, text in raw.items():
        if not isinstance(state, str):
            continue
        if states and state not in states:
            continue
        if not isinstance(text, str):
            continue
        text = text[:_MAX_STAGE_OVERRIDE_VALUE_CHARS]
        if not text.strip():
            continue
        total += len(text.encode("utf-8", errors="ignore"))
        if total > _MAX_STAGE_OVERRIDES_TOTAL_BYTES:
            break
        out[state] = text
    return out
