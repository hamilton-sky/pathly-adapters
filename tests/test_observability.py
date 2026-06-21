"""Tests for pathly-observability Conv 1: /record_phase endpoint and exempt_prefixes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app, _rate_counters

    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def _feature_dir(tmp_path: Path, feature: str = "my-feature") -> Path:
    d = tmp_path / "pathly" / "plans" / feature
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── /record_phase — valid PHASE_START ─────────────────────────────────────────


def test_record_phase_start_valid(client):
    c, tmp_path = client
    feature_dir = _feature_dir(tmp_path)

    r = c.post(
        "/record_phase",
        json={
            "feature": "my-feature",
            "agent": "builder",
            "phase": "implement",
            "event_type": "PHASE_START",
            "project_root": str(tmp_path),
        },
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data == {"status": "recorded"}

    from pathly_orchestrator import eventlog as _eventlog

    events = _eventlog.read_events(str(feature_dir))
    assert len(events) == 1
    line = events[0]
    assert line["schema_version"] == 1
    assert line["type"] == "PHASE_START"
    assert line["phase"] == "implement"
    assert line["agent"] == "builder"
    assert line["feature"] == "my-feature"
    assert "ts" in line
    # conv not supplied — should be absent
    assert "conv" not in line


# ── /record_phase — valid PHASE_DONE with all optional fields ─────────────────


def test_record_phase_done_all_optional_fields(client):
    c, tmp_path = client
    feature_dir = _feature_dir(tmp_path)

    r = c.post(
        "/record_phase",
        json={
            "feature": "my-feature",
            "agent": "builder",
            "phase": "implement",
            "event_type": "PHASE_DONE",
            "conv": 2,
            "total_tokens": 1500,
            "tool_uses": 7,
            "scouts_count": 3,
            "summary": "implemented the feature",
            "project_root": str(tmp_path),
        },
    )
    assert r.status_code == 200

    from pathly_orchestrator import eventlog as _eventlog

    events = _eventlog.read_events(str(feature_dir))
    assert len(events) == 1
    line = events[0]
    assert line["type"] == "PHASE_DONE"
    assert line["conv"] == 2
    assert line["total_tokens"] == 1500
    assert line["tool_uses"] == 7
    assert line["scouts_count"] == 3
    assert line["summary"] == "implemented the feature"
    assert "ts" in line


# ── /record_phase — missing required field → 400 ──────────────────────────────


@pytest.mark.parametrize("missing_field", ["feature", "agent", "phase", "event_type"])
def test_record_phase_missing_required_field(client, missing_field):
    c, tmp_path = client
    _feature_dir(tmp_path)

    body = {
        "feature": "my-feature",
        "agent": "builder",
        "phase": "implement",
        "event_type": "PHASE_START",
        "project_root": str(tmp_path),
    }
    del body[missing_field]

    r = c.post("/record_phase", json=body)
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data


# ── /record_phase — invalid event_type → 400 ──────────────────────────────────


def test_record_phase_invalid_event_type(client):
    c, tmp_path = client
    _feature_dir(tmp_path)

    r = c.post(
        "/record_phase",
        json={
            "feature": "my-feature",
            "agent": "builder",
            "phase": "implement",
            "event_type": "AGENT_DONE",
            "project_root": str(tmp_path),
        },
    )
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data
    assert "event_type" in data["error"]


# ── /record_phase — invalid phase value → 400 ─────────────────────────────────


def test_record_phase_invalid_phase(client):
    c, tmp_path = client
    _feature_dir(tmp_path)

    r = c.post(
        "/record_phase",
        json={
            "feature": "my-feature",
            "agent": "builder",
            "phase": "deploy",
            "event_type": "PHASE_START",
            "project_root": str(tmp_path),
        },
    )
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data
    assert "phase" in data["error"]


# ── _is_exempt with exempt_prefixes in flow ───────────────────────────────────


def test_scope_clean_extra_prefix_recognized(tmp_path, monkeypatch):
    """A path matching a YAML-defined exempt_prefix is not flagged as a violation."""
    import pathly_orchestrator.fsm as fsm_mod
    from pathly_orchestrator.fsm import _scope_clean

    storage = tmp_path / "pathly" / "plans" / "feat"
    storage.mkdir(parents=True, exist_ok=True)

    scope_md = storage / "SCOPE.md"
    scope_md.write_text("Files:\n- `src/app.py`\n", encoding="utf-8")

    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **_):
        if "diff" in args:
            # src/app.py is declared; pathly/pipeline-walkthrough/ is exempt via YAML
            return type(
                "R",
                (),
                {
                    "returncode": 0,
                    "stdout": "src/app.py\npathly/pipeline-walkthrough/feat/artifacts/x.md\n",
                    "stderr": "",
                },
            )()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow_with_extra = {
        "scope_gate": {"exempt_prefixes": ["pathly/pipeline-walkthrough/"]}
    }
    result = _scope_clean(storage, "SCOPE.md", set(), flow=flow_with_extra)
    assert result is True


def test_scope_clean_exempt_prefixes_absent_unchanged(tmp_path, monkeypatch):
    """When scope_gate.exempt_prefixes is absent, behavior is identical to today."""
    import pathly_orchestrator.fsm as fsm_mod
    from pathly_orchestrator.fsm import _scope_clean

    storage = tmp_path / "pathly" / "plans" / "feat"
    storage.mkdir(parents=True, exist_ok=True)

    scope_md = storage / "SCOPE.md"
    scope_md.write_text("Files:\n- `src/app.py`\n", encoding="utf-8")

    def fake_run(args, **_):
        if "diff" in args:
            return type(
                "R",
                (),
                {
                    "returncode": 0,
                    "stdout": "src/app.py\nsrc/SURPRISE.py\n",
                    "stderr": "",
                },
            )()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    # No flow passed — falls back to hardcoded defaults only
    result = _scope_clean(storage, "SCOPE.md", set(), flow=None)
    assert result is False


def test_scope_clean_hardcoded_defaults_still_exempt(tmp_path, monkeypatch):
    """pathly/plans/ and .tsbuildinfo remain exempt even when exempt_prefixes is empty."""
    import pathly_orchestrator.fsm as fsm_mod
    from pathly_orchestrator.fsm import _scope_clean

    storage = tmp_path / "pathly" / "plans" / "feat"
    storage.mkdir(parents=True, exist_ok=True)

    scope_md = storage / "SCOPE.md"
    scope_md.write_text("Files:\n- `src/app.py`\n", encoding="utf-8")

    def fake_run(args, **_):
        if "diff" in args:
            return type(
                "R",
                (),
                {
                    "returncode": 0,
                    "stdout": "src/app.py\npathly/plans/feat/EVENTS.jsonl\nstudio/build.tsbuildinfo\n",
                    "stderr": "",
                },
            )()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow_with_empty = {"scope_gate": {"exempt_prefixes": []}}
    result = _scope_clean(storage, "SCOPE.md", set(), flow=flow_with_empty)
    assert result is True
