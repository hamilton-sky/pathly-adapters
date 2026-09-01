"""The pathly-* CLI shortcuts' SECOND discovery source: compiled-flow runs.

A compiled-flow run (supervisor/compiled_flow.py) writes no fsm_state and no STATE.json,
so cli/_discovery.py's disk globs cannot see it. cli/_compiled.py finds it in run_history
instead. These tests use the REAL writer (db.queries.run_history.upsert_run) and the real
app-setting, so they exercise the same rows a live run produces.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pathly_orchestrator.cli._compiled import (
    describe_compiled_run,
    exit_no_features,
    exit_topic_not_found,
    find_compiled_run,
    latest_compiled_runs,
)


def _set_compiled(value: str) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "flow.compiled_executors", value)


def _run(root: Path, feature: str, flow: str, status: str = "running", **kw) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_history import upsert_run

    run_id = kw.pop("run_id", f"{feature}-{flow}-{status}")
    upsert_run(
        get_db(),
        project_root=str(root),
        feature=feature,
        run_id=run_id,
        status=status,
        adapter=flow,
        **kw,
    )
    return run_id


def _mk_state(root: Path, rel: str, state: str = "BUILDING") -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "STATE.json").write_text(json.dumps({"current": state}), encoding="utf-8")
    return d


# ── latest_compiled_runs ──────────────────────────────────────────────────────────


def test_unconfigured_setting_finds_nothing(tmp_path):
    """Off by default: a quick-fix run exists, but no flow is opted in, so the CLI
    keeps its pre-Phase-2 behavior exactly."""
    _run(tmp_path, "fix-a", "quick-fix")
    assert latest_compiled_runs(tmp_path) == []


def test_finds_compiled_run(tmp_path):
    _set_compiled("quick-fix,debug")
    _run(tmp_path, "fix-a", "quick-fix", stage_count=3, cost_usd=0.25)
    runs = latest_compiled_runs(tmp_path)
    assert len(runs) == 1
    assert runs[0]["topic"] == "fix-a"
    assert runs[0]["flow"] == "quick-fix"
    assert runs[0]["stage_count"] == 3
    assert runs[0]["cost_usd"] == pytest.approx(0.25)
    assert runs[0]["compiled"] is True


def test_ignores_flows_not_opted_in(tmp_path):
    """run_history.adapter carries the flow name for EVERY supervised run — only the
    ones listed in flow.compiled_executors are stateless."""
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix")
    _run(tmp_path, "feat-b", "team")
    assert [r["topic"] for r in latest_compiled_runs(tmp_path)] == ["fix-a"]


def test_ignores_other_project_roots(tmp_path):
    _set_compiled("quick-fix")
    _run(tmp_path / "elsewhere", "fix-other", "quick-fix")
    _run(tmp_path, "fix-here", "quick-fix")
    assert [r["topic"] for r in latest_compiled_runs(tmp_path)] == ["fix-here"]


def test_one_entry_per_topic_newest_wins(tmp_path):
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix", status="error", run_id="r1")
    _run(tmp_path, "fix-a", "quick-fix", status="done", run_id="r2")
    runs = latest_compiled_runs(tmp_path)
    assert len(runs) == 1
    assert runs[0]["status"] == "done"
    assert runs[0]["run_id"] == "r2"


def test_legacy_path_rows_resolve_to_their_slug(tmp_path):
    """Rows written before run_history was keyed by slug hold a full path (see
    run_history._SLUG_MATCH); the basename is the topic either way."""
    _set_compiled("debug")
    _run(tmp_path, "pathly/features/parent/debugs/bug-x", "debug")
    assert [r["topic"] for r in latest_compiled_runs(tmp_path)] == ["bug-x"]


def test_fails_safe_when_db_is_unreachable(tmp_path, monkeypatch):
    """These are human shortcuts — a DB-less cwd must degrade to "nothing", never crash."""
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix")
    import pathly_orchestrator.db.connection as conn_mod

    monkeypatch.setattr(
        conn_mod, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert latest_compiled_runs(tmp_path) == []
    assert find_compiled_run(tmp_path, "fix-a") is None


def test_find_compiled_run_by_topic(tmp_path):
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix")
    assert find_compiled_run(tmp_path, "fix-a")["topic"] == "fix-a"
    assert find_compiled_run(tmp_path, "nope") is None


# ── pathly-status merge ───────────────────────────────────────────────────────────


def test_status_lists_a_compiled_run_with_no_state_file(tmp_path):
    from pathly_orchestrator.cli.status import _scan

    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix", stage_count=2)
    active, done = _scan(tmp_path)
    assert [e["topic"] for e in active] == ["fix-a"]
    assert active[0]["state"] == "RUNNING"
    assert done == []


def test_status_buckets_a_finished_compiled_run_as_done(tmp_path):
    from pathly_orchestrator.cli.status import _scan

    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix", status="done")
    active, done = _scan(tmp_path)
    assert active == []
    assert [e["topic"] for e in done] == ["fix-a"]


def test_status_prefers_disk_state_over_run_history(tmp_path):
    """A flow opted in AFTER some FSM-driven history has rows in both sources. The disk
    one is authoritative for that topic — it must not also appear as a stateless run."""
    from pathly_orchestrator.cli.status import _scan

    _set_compiled("quick-fix")
    _mk_state(tmp_path, "pathly/features/fix-a", state="REVIEWING")
    _run(tmp_path, "fix-a", "quick-fix", status="error")
    active, _done = _scan(tmp_path)
    assert len(active) == 1
    assert active[0]["state"] == "REVIEWING"
    assert not active[0].get("compiled")


def test_status_row_labels_a_compiled_run(tmp_path):
    from pathly_orchestrator.cli.status import _render_row

    row = _render_row(
        {
            "topic": "fix-a",
            "flow": "quick-fix",
            "state": "RUNNING",
            "conv": 1,
            "feedback": None,
            "compiled": True,
        }
    )
    assert "compiled · 1 stage)" in row  # singular, and never "conv"
    assert "conv" not in row


# ── log / back / ff diagnostics ───────────────────────────────────────────────────


def test_unknown_topic_still_reports_not_found(tmp_path, capsys):
    _set_compiled("quick-fix")
    with pytest.raises(SystemExit) as exc:
        exit_topic_not_found(tmp_path, "ghost", "show")
    assert exc.value.code == 1
    assert "not found in any scan root" in capsys.readouterr().out


def test_compiled_topic_is_explained_not_called_missing(tmp_path, capsys):
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix", status="done", stage_count=2)
    with pytest.raises(SystemExit) as exc:
        exit_topic_not_found(tmp_path, "fix-a", "roll back")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "not found in any scan root" not in out
    assert "compiled-flow executor" in out
    assert "nothing to roll back" in out


def test_no_features_message_when_nothing_exists(tmp_path, capsys):
    with pytest.raises(SystemExit):
        exit_no_features(tmp_path, "show")
    assert "No active features found." in capsys.readouterr().out


def test_no_features_names_the_compiled_run_instead(tmp_path, capsys):
    _set_compiled("debug")
    _run(tmp_path, "bug-x", "debug")
    with pytest.raises(SystemExit):
        exit_no_features(tmp_path, "fast-forward")
    out = capsys.readouterr().out
    assert "No active features found." not in out
    assert "bug-x" in out


def test_describe_reports_status_stages_and_cost(tmp_path):
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix", status="error", stage_count=4, cost_usd=1.5)
    lines = "\n".join(describe_compiled_run(find_compiled_run(tmp_path, "fix-a")))
    assert "error" in lines and "4 stage(s)" in lines and "$1.50" in lines


@pytest.mark.parametrize(
    "module,action",
    [("log", "show"), ("back", "roll back"), ("ff", "fast-forward")],
)
def test_cli_entrypoint_explains_a_compiled_topic(
    tmp_path, capsys, monkeypatch, module, action
):
    """End-to-end through each command's own main(): a compiled topic is diagnosed, and
    ff in particular never reaches next_action (which would mint the fsm_state that makes
    the compiled executor refuse to re-run this topic)."""
    import importlib

    mod = importlib.import_module(f"pathly_orchestrator.cli.{module}")
    _set_compiled("quick-fix")
    _run(tmp_path, "fix-a", "quick-fix")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [f"pathly-{module}", "fix-a"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "compiled-flow executor" in out
    assert f"nothing to {action}" in out
