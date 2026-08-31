"""Shared plumbing for gate checks — event append, feedback write, failure result.

Every gate check returns ``None`` to let the transition proceed, or the dict produced by
:func:`gate_failed` to block it. Keeping that shape in one place is what lets
``run_gates`` stay a pure dispatcher.
"""

from __future__ import annotations

from pathlib import Path


def append_event(storage_path: Path, event: dict, flow: dict | None = None) -> None:
    from pathly_orchestrator.eventlog import append_event as _append_event

    _append_event(str(storage_path), event, flow=flow)


def _write_gate_feedback(storage_path: Path, on_fail: str, reason: str) -> None:
    feedback_dir = storage_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    target = feedback_dir / on_fail
    target.write_text(reason, encoding="utf-8")


def gate_failed(
    storage_path: Path,
    gate: dict,
    gtype: str,
    prev_state: str,
    next_state: str,
    reason: str,
    extra: dict | None = None,
) -> dict:
    """Write the feedback file, log GATE_FAILED, and return the blocking result."""
    _write_gate_feedback(storage_path, gate["on_fail"], reason)
    event = {
        "type": "GATE_FAILED",
        "gate": gtype,
        "transition": f"{prev_state}->{next_state}",
    }
    if extra:
        event.update(extra)
    append_event(storage_path, event)
    return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}


def gate_skipped(storage_path: Path, gtype: str, reason: str) -> None:
    """Log that a gate did not run. Fail-open: absent config never wedges a run."""
    append_event(
        storage_path, {"type": "GATE_SKIPPED", "gate": gtype, "reason": reason}
    )


def project_root_of(storage_path: Path) -> Path:
    """Repo root for a run dir at ANY nesting depth (flat feature or nested goal/kind).

    Delegates to the eventlog resolver so the gate, the event log and ``fsm_state`` all key
    off the SAME root — a nested ``goals/<slug>`` run must not resolve three levels up into
    ``pathly/features``.
    """
    from pathly_orchestrator.eventlog import _project_root_of

    return Path(_project_root_of(storage_path))
