"""Tests for Conv 2: STATE.json schema validation, state/transition enforcement, concurrency."""

from __future__ import annotations
import json
import threading
import tempfile
from pathlib import Path

import jsonschema
import pytest

from _paths import SRC
from pathly_orchestrator.state import VALID_STATES, TRANSITIONS, STATES
from pathly_orchestrator import eventlog as el

SCHEMA_PATH = SRC / "pathly_data" / "schemas" / "state.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ── Schema validation ─────────────────────────────────────────────────────────


def _valid_state_doc(**overrides) -> dict:
    base = {
        "current": "BUILDING",
        "feature": "test-feature",
        "rigor": "lite",
        "updated_at": "2026-05-13T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_schema_validates_good_document():
    jsonschema.validate(_valid_state_doc(), SCHEMA)


def test_schema_rejects_unknown_state():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_valid_state_doc(current="INVALID_STATE"), SCHEMA)


def test_schema_rejects_missing_required_field():
    doc = _valid_state_doc()
    del doc["current"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, SCHEMA)


def test_schema_rejects_unknown_rigor():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_valid_state_doc(rigor="experimental"), SCHEMA)


def test_schema_accepts_all_13_states():
    for state in VALID_STATES:
        jsonschema.validate(_valid_state_doc(current=state), SCHEMA)


def test_schema_transitions_covers_all_states():
    transitions = SCHEMA["transitions"]
    assert set(transitions.keys()) == set(STATES.keys())


def test_iteration_by_stage_is_optional():
    # Existing STATE.json files that omit iteration_by_stage must still validate.
    jsonschema.validate(_valid_state_doc(), SCHEMA)
    # Documents that include iteration_by_stage must also validate.
    jsonschema.validate(_valid_state_doc(iteration_by_stage={"BUILDING": 2}), SCHEMA)


# ── write_state validation ────────────────────────────────────────────────────


def test_write_state_rejects_invalid_state_name(tmp_path):
    with pytest.raises(ValueError, match="Invalid state"):
        el.write_state.__wrapped__(
            tmp_path, "test", {"current": "BOGUS", "feature": "x", "rigor": "lite"}
        )


def _write_state_in_tmp(tmp_path: Path, feature: str, state_dict: dict):
    """Call write_state with plans/ rooted at tmp_path."""
    original_plans = el._plans_dir

    def _patched():
        return tmp_path / "plans"

    el._plans_dir = _patched
    try:
        el.write_state(feature, state_dict)
    finally:
        el._plans_dir = original_plans


def _append_event_in_tmp(tmp_path: Path, feature: str, event: dict):
    original_plans = el._plans_dir

    def _patched():
        return tmp_path / "plans"

    el._plans_dir = _patched
    try:
        el.append_event(feature, event)
    finally:
        el._plans_dir = original_plans


def _read_events_in_tmp(tmp_path: Path, feature: str) -> list[dict]:
    original_plans = el._plans_dir

    def _patched():
        return tmp_path / "plans"

    el._plans_dir = _patched
    try:
        return el.read_events(feature)
    finally:
        el._plans_dir = original_plans


def test_write_state_rejects_invalid_state_name(tmp_path):
    with pytest.raises(ValueError, match="Invalid state"):
        _write_state_in_tmp(
            tmp_path, "feat", {"current": "BOGUS", "feature": "feat", "rigor": "lite"}
        )


def test_write_state_accepts_valid_state(tmp_path):
    _write_state_in_tmp(
        tmp_path, "feat", {"current": "BUILDING", "feature": "feat", "rigor": "lite"}
    )
    # Read back via public API — works in both normal and PATHLY_DB_ONLY=1 mode
    original_plans = el._plans_dir
    el._plans_dir = lambda: tmp_path / "plans"
    try:
        result = el.read_state("feat")
    finally:
        el._plans_dir = original_plans
    assert result is not None
    assert result["current"] == "BUILDING"


def test_write_state_rejects_illegal_transition(tmp_path):
    _write_state_in_tmp(
        tmp_path, "feat", {"current": "BUILDING", "feature": "feat", "rigor": "lite"}
    )
    with pytest.raises(ValueError, match="Invalid state transition"):
        _write_state_in_tmp(
            tmp_path,
            "feat",
            {"current": "PLANNING", "feature": "feat", "rigor": "lite"},
        )


def test_write_state_allows_legal_transition(tmp_path):
    _write_state_in_tmp(
        tmp_path, "feat", {"current": "BUILDING", "feature": "feat", "rigor": "lite"}
    )
    _write_state_in_tmp(
        tmp_path, "feat", {"current": "REVIEWING", "feature": "feat", "rigor": "lite"}
    )


# ── append_event validation ───────────────────────────────────────────────────


def test_append_event_rejects_invalid_to_state(tmp_path):
    with pytest.raises(ValueError, match="Invalid state in STATE_TRANSITION"):
        _append_event_in_tmp(
            tmp_path, "feat", {"type": "STATE_TRANSITION", "to": "GARBAGE"}
        )


def test_append_event_accepts_valid_to_state(tmp_path):
    _append_event_in_tmp(
        tmp_path, "feat", {"type": "STATE_TRANSITION", "to": "BUILDING"}
    )
    events = _read_events_in_tmp(tmp_path, "feat")
    assert len(events) == 1
    assert events[0]["to"] == "BUILDING"


def test_append_event_non_transition_not_validated(tmp_path):
    _append_event_in_tmp(tmp_path, "feat", {"type": "AGENT_DONE", "result": "ok"})
    events = _read_events_in_tmp(tmp_path, "feat")
    assert len(events) == 1


# ── TRANSITIONS constant ──────────────────────────────────────────────────────


def test_transitions_covers_all_states():
    assert set(TRANSITIONS.keys()) == set(STATES.keys())


def test_transitions_targets_are_valid_states():
    for src, targets in TRANSITIONS.items():
        for t in targets:
            assert t in VALID_STATES, f"{src} → {t} is not a valid state"


# ── Concurrent append stress test ────────────────────────────────────────────


def test_concurrent_append_produces_500_valid_lines(tmp_path):
    """10 threads × 50 appends must yield exactly 500 valid events.

    Regression test for two real Windows concurrency bugs this used to flake on
    (the count came back 498–499, varying run-to-run). NO writes were ever lost —
    the rows were all in the DB — but they were unreadable:

    1. project_root key split (fsm_events._norm) — `Path.resolve()` on Windows
       returns the ``\\\\?\\`` extended-length prefix inconsistently, notably for a
       not-yet-created dir racing directory creation, so a feature's first event(s)
       were written under ``//?/C:/...`` while the reader queried ``C:/...`` and
       missed them. _norm now strips the prefix so every form is one key.
    2. connection-open race (db.connection.get_db) — `PRAGMA journal_mode=WAL`
       briefly needs an exclusive lock, so concurrent first-time opens raised
       "database is locked"; connection creation is now serialized under the
       global write lock.

    The tmp plans-dir is also patched ONCE around the whole block (not per call
    inside each worker, which mutated a shared module global from 10 threads).
    """
    THREADS = 10
    EVENTS_PER_THREAD = 50
    feature = "stress-test"

    errors: list[Exception] = []

    def worker(thread_id: int):
        try:
            for i in range(EVENTS_PER_THREAD):
                el.append_event(
                    feature,
                    {"type": "AGENT_DONE", "thread": thread_id, "seq": i},
                )
        except Exception as exc:
            errors.append(exc)

    original_plans = el._plans_dir
    el._plans_dir = lambda: tmp_path / "plans"
    try:
        threads = [
            threading.Thread(target=worker, args=(tid,)) for tid in range(THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

        events = el.read_events(feature)
    finally:
        el._plans_dir = original_plans

    assert (
        len(events) == THREADS * EVENTS_PER_THREAD
    ), f"Expected {THREADS * EVENTS_PER_THREAD} events, got {len(events)}"
    for e in events:
        assert isinstance(e, dict)
        assert e["type"] == "AGENT_DONE"
