"""Layout invariant: EVERY subsystem locates a feature at its ONE canonical home.

This is the safety net for the storage-path consolidation (production-readiness T2/T3 +
storage-restructure-p2 T6). After the storage flatten, a feature's canonical home is the
FLAT ``pathly/features/<name>/`` directory. Historically many subsystems hard-coded the
legacy ``pathly/plans/<name>/`` base, so they read/write the WRONG tree for a current
feature (the same class of bug that made CLI discovery find none of the live features).

The invariant: create a feature the canonical way, then assert that discovery, the FSM
resolver, the goal-dir resolver, and every event/telemetry/health/feedback code path all
agree the feature lives at ``pathly/features/<name>/`` — never ``pathly/plans/<name>/``.

Several assertions here FAIL against pre-consolidation code on purpose — that failure IS
the spec. As each site is routed through the shared resolver they go green, one at a time.
Assertions marked "regression guard" already pass (discovery + goal-dir already flattened).
"""

from __future__ import annotations

from pathlib import Path

import pytest


FEATURE = "layout-inv-feature"


# ── canonical feature fixture ────────────────────────────────────────────────


def _make_feature(root: Path, name: str = FEATURE) -> Path:
    """Stand up a feature the CANONICAL way: pathly/features/<name>/ with the files the
    live team pipeline reads/writes (STATE.json via the real writer → DB row + file mirror,
    EVENTS.jsonl, PROGRESS.md, feedback/). Returns the feature dir. Deliberately creates NO
    pathly/plans/<name> — a subsystem that only finds the feature under plans/ must fail."""
    from pathly_orchestrator import eventlog

    feature_dir = root / "pathly" / "features" / name
    feature_dir.mkdir(parents=True, exist_ok=True)
    # Real writer: persists the DB fsm_state row (what read_state queries) AND STATE.json.
    eventlog.write_state(
        str(feature_dir),
        {"current": "BUILDING", "feature": name, "rigor": "lite"},
    )
    (feature_dir / "EVENTS.jsonl").touch()
    (feature_dir / "PROGRESS.md").write_text("# Progress\n", encoding="utf-8")
    (feature_dir / "feedback").mkdir(exist_ok=True)
    return feature_dir


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask test client with an isolated project root (DB is isolated by conftest)."""
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app, _rate_counters

    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def _plans(root: Path, name: str = FEATURE) -> Path:
    return root / "pathly" / "plans" / name


# ── the resolvers (the ONE home) ─────────────────────────────────────────────


def test_resolver_resolves_flat_feature(tmp_path):
    """fsm_ops._resolve_storage_path is THE feature-dir resolver. It must resolve the flat
    home for an existing feature, and — flow-less (flow_config=None) — default a not-yet-created
    feature to pathly/features/<topic>, never pathly/plans/<topic>."""
    import pathly_orchestrator.fsm_ops as fsm_ops

    feature_dir = _make_feature(tmp_path)
    assert fsm_ops._resolve_storage_path(None, str(tmp_path), FEATURE) == feature_dir

    # Not-yet-created feature, no flow → canonical features/ default (FAILS today: None flow).
    ghost = fsm_ops._resolve_storage_path(None, str(tmp_path), "ghost-feature")
    assert ghost == tmp_path / "pathly" / "features" / "ghost-feature"


def test_discovery_finds_flat_feature(tmp_path):
    """Regression guard: CLI discovery already handles the flat layout — keep it that way."""
    from pathly_orchestrator.cli._discovery import find_topic_dir

    feature_dir = _make_feature(tmp_path)
    result = find_topic_dir(tmp_path, FEATURE)
    assert result is not None
    storage_path, flow = result
    assert storage_path == feature_dir
    assert flow == "team"


def test_goal_storage_dir_is_nested_not_flat(tmp_path):
    """Regression guard for T6's canonical answer: a feature-tier goal nests under its
    feature; the flat pathly/goals/<slug> home is gone. The goal-executor loop MUST match."""
    from pathly_orchestrator.supervisor.goal_decomposer import _goal_storage_dir

    d = _goal_storage_dir(str(tmp_path), "feature", FEATURE, "goal-slug").replace("\\", "/")
    assert d.endswith(f"pathly/features/{FEATURE}/goals/goal-slug")
    assert "pathly/goals/" not in d


# ── event / telemetry / health / feedback code paths ─────────────────────────


def test_status_endpoint_finds_flat_feature(client):
    """/status must report a feature that lives ONLY under features/. Pre-consolidation it
    short-circuits to 'no-feature' because pathly/plans/ does not exist."""
    c, root = client
    _make_feature(root)
    assert not _plans(root).exists()

    r = c.get(f"/status?project_root={root}&topic={FEATURE}")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("current_state") != "no-feature"
    assert data.get("feature") == FEATURE


def test_record_phase_lands_in_features_dir(client):
    """/record_phase resolves the feature dir to gate + write its PHASE event. Pre-consolidation
    it checks pathly/plans/<feature> (absent) and 400s; the event never lands."""
    c, root = client
    _make_feature(root)

    r = c.post(
        "/record_phase",
        json={
            "feature": FEATURE,
            "agent": "builder",
            "phase": "implement",
            "event_type": "PHASE_START",
            "project_root": str(root),
        },
    )
    assert r.status_code == 200, r.data

    from pathly_orchestrator import eventlog

    events = eventlog.read_events(str(root / "pathly" / "features" / FEATURE))
    assert any(e.get("type") == "PHASE_START" for e in events)
    assert not _plans(root).exists()


def test_record_activity_lands_in_features_dir(tmp_path):
    """The AGENT_DONE telemetry writer gates on the feature dir existing. Pre-consolidation it
    looks under plans/ (absent) and silently drops the event."""
    _make_feature(tmp_path)
    from pathly_orchestrator.http_server.blueprints.ops.telemetry_activity import (
        _append_agent_done_event,
    )

    _append_agent_done_event(
        project_root=str(tmp_path),
        feature=FEATURE,
        agent="builder",
        model="claude-sonnet-4-6",
        result="did the thing",
        conversation=None,
        total_tokens=10,
        tokens_in=6,
        tokens_out=4,
        tool_uses=1,
        wall_seconds=2,
        cost_usd=0.0,
    )

    from pathly_orchestrator import eventlog

    events = eventlog.read_events(str(tmp_path / "pathly" / "features" / FEATURE))
    assert any(e.get("type") == "AGENT_DONE" for e in events)
    assert not _plans(tmp_path).exists()


def test_runner_event_writes_features_not_plans(client):
    """POST /runner/event must materialize the event under features/, not spawn a stray
    pathly/plans/<feature> tree."""
    c, root = client
    _make_feature(root)

    r = c.post(
        "/runner/event",
        json={
            "type": "NOTE",
            "feature": FEATURE,
            "project_root": str(root),
            "payload": {"type": "NOTE", "text": "hi"},
        },
    )
    assert r.status_code == 200, r.data
    assert not _plans(root).exists()


def test_runner_event_creates_no_decoy_for_absent_feature(client):
    """/runner/event records the event to the DB WITHOUT materializing a feature dir for a
    topic that has no features/ home (a debug/fix/goal run whose storage lives elsewhere).
    A stray empty pathly/features/<topic> would win _resolve_storage_path's existence probe
    and hijack that topic's real storage on the next resolve — the class of bug the flat
    _write_mirror mkdir caused. The event is DB-keyed, so it persists with no dir at all."""
    c, root = client
    topic = "debug-topic-no-home"  # deliberately created nowhere on disk

    r = c.post(
        "/runner/event",
        json={
            "type": "AGENT_DONE",
            "feature": topic,
            "project_root": str(root),
            "payload": {"type": "AGENT_DONE", "summary": "did debug work"},
        },
    )
    assert r.status_code == 200, r.data
    # No decoy dir under features/ OR plans/ — nothing was materialized.
    assert not (root / "pathly" / "features" / topic).exists()
    assert not (root / "pathly" / "plans" / topic).exists()
    # …yet the event is recorded (DB keyed by project_root + feature name).
    from pathly_orchestrator import eventlog

    events = eventlog.read_events(str(root / "pathly" / "features" / topic))
    assert any(e.get("type") == "AGENT_DONE" for e in events)


def test_eventlog_keys_nested_run_by_true_project_root(tmp_path):
    """board-scoped-storage FOUNDATION: eventlog keys fsm_state by (project_root, feature). It must
    derive the REAL project root for a run NESTED under its board — the legacy '3 levels up' rule
    mis-derives <root>/pathly for a project/<kind>/<slug> run (and <root>/pathly/features for a
    feature-nested run), orphaning the authoritative DB row from the true root. That split-brain is
    what breaks both a folder move AND P1's new nested runs. Assert the stored key is the true root,
    not a depth artifact."""
    from pathly_orchestrator import eventlog

    true_root = str(tmp_path).replace("\\", "/")
    conn = eventlog._db.get_db()

    proj_run = tmp_path / "pathly" / "project" / "explorations" / "nested-proj-run"
    feat_run = tmp_path / "pathly" / "features" / "some-feat" / "debugs" / "nested-feat-run"
    for run_dir in (proj_run, feat_run):
        run_dir.mkdir(parents=True)
        eventlog.write_state(str(run_dir), {"current": "DONE", "feature": run_dir.name})

    keyed = {
        r[1]: r[0]
        for r in conn.execute(
            "SELECT project_root, feature FROM fsm_state "
            "WHERE feature IN ('nested-proj-run','nested-feat-run')"
        )
    }
    assert keyed.get("nested-proj-run") == true_root, keyed
    assert keyed.get("nested-feat-run") == true_root, keyed


def test_discovery_finds_board_nested_runs(tmp_path):
    """board-scoped-storage P3: a run nested under its board — feature (features/<f>/<kind>/<slug>)
    or project (project/<kind>/<slug>) — must be discoverable, so moving a legacy shared-bucket run
    under its board does not make it vanish from `/pathly status` & friends."""
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.cli._discovery import find_topic_dir, iter_state_files

    feat_run = tmp_path / "pathly" / "features" / "feat-x" / "explorations" / "trace-1"
    feat_run.mkdir(parents=True)
    eventlog.write_state(str(feat_run), {"current": "DONE", "feature": "trace-1"})

    proj_run = tmp_path / "pathly" / "project" / "debugs" / "bug-1"
    proj_run.mkdir(parents=True)
    eventlog.write_state(str(proj_run), {"current": "DONE", "feature": "bug-1"})

    found = {(sf.parent.resolve(), flow, topic) for sf, flow, topic in iter_state_files(tmp_path)}
    assert (feat_run.resolve(), "explore", "trace-1") in found
    assert (proj_run.resolve(), "debug", "bug-1") in found
    # named lookup resolves the project run to its nested home
    assert find_topic_dir(tmp_path, "bug-1") == (proj_run, "debug")


def test_feedback_watcher_scans_features(tmp_path):
    """The feedback watcher must discover feedback files under a flat feature home. Pre-
    consolidation it globs pathly/plans/*/feedback/*.md only and never sees them."""
    feature_dir = _make_feature(tmp_path)
    fb = feature_dir / "feedback" / "REVIEW_FAILURES.md"
    fb.write_text("REVIEW FAILED\n", encoding="utf-8")

    from pathly_orchestrator.http_server import feedback as _fb

    found = {Path(p).resolve() for p in _fb._iter_feedback_files(str(tmp_path))}
    assert fb.resolve() in found
