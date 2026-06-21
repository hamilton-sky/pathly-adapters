import pytest
from unittest.mock import patch


def _make_test_db(tmp_path, n_events=2):
    from pathly_orchestrator import db as _db

    feature = "test-feature"
    feature_dir = tmp_path / "pathly" / "plans" / feature
    feature_dir.mkdir(parents=True)
    conn = _db.get_db()
    project_root = str(tmp_path)
    for i in range(n_events):
        _db.append_event(
            conn,
            project_root,
            feature,
            {
                "type": "AGENT_DONE",
                "agent": "builder",
                "feature": feature,
                "ts": "2026-01-01T00:00:00Z",
                "result": "pass",
                "tokens_in": 100,
                "tokens_out": 50,
                "cost_usd": 0.001,
                "wall_seconds": 30,
                "model": "claude-sonnet-4-6",
                "conversation": i + 1,
            },
        )
    return feature_dir, feature


def _run_cli(argv):
    """Run cli_main() with the given sys.argv and return the SystemExit raised."""
    from pathly_orchestrator.otel_export import cli_main

    with patch("sys.argv", argv):
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
    return exc_info.value


def test_cli_missing_db(tmp_path):
    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            "nonexistent",
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert exit_exc.code == 1


def test_cli_dry_run(tmp_path, monkeypatch, capsys):
    _make_test_db(tmp_path, n_events=2)
    calls = []
    monkeypatch.setattr(
        "pathly_orchestrator.otel_export._do_export",
        lambda event, endpoint: calls.append((event, endpoint)),
    )
    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            "test-feature",
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert exit_exc.code == 0
    assert len(calls) == 0
    captured = capsys.readouterr()
    assert "dry-run" in captured.out
    assert "exported span:" not in captured.out


def test_cli_exports_spans(tmp_path, monkeypatch, capsys):
    _make_test_db(tmp_path, n_events=2)
    calls = []
    monkeypatch.setattr(
        "pathly_orchestrator.otel_export._do_export",
        lambda event, endpoint: calls.append((event, endpoint)),
    )
    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            "test-feature",
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert exit_exc.code == 0
    assert len(calls) == 2
    captured = capsys.readouterr()
    assert "exported span:" in captured.out


def test_cli_zero_events(tmp_path, capsys):
    from pathly_orchestrator import db as _db

    feature = "test-feature"
    feature_dir = tmp_path / "pathly" / "plans" / feature
    feature_dir.mkdir(parents=True)
    conn = _db.get_db()
    _db.append_event(
        conn,
        str(tmp_path),
        feature,
        {
            "type": "PHASE_START",
            "feature": feature,
            "ts": "2026-01-01T00:00:00Z",
        },
    )

    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            feature,
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert exit_exc.code == 0
    captured = capsys.readouterr()
    assert "done: 0 spans exported" in captured.out


def test_cli_export_failure_exits_1(tmp_path, monkeypatch):
    _make_test_db(tmp_path, n_events=2)

    def _raise(*_: object) -> None:
        raise OSError("network error")

    monkeypatch.setattr(
        "pathly_orchestrator.otel_export._do_export",
        _raise,
    )
    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            "test-feature",
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert exit_exc.code == 1


def test_cli_non_agent_done_events_skipped(tmp_path, monkeypatch):
    from pathly_orchestrator import db as _db

    feature = "test-feature"
    feature_dir = tmp_path / "pathly" / "plans" / feature
    feature_dir.mkdir(parents=True)
    conn = _db.get_db()
    project_root = str(tmp_path)
    _db.append_event(
        conn,
        project_root,
        feature,
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "feature": feature,
            "ts": "2026-01-01T00:00:00Z",
            "result": "pass",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.001,
            "wall_seconds": 30,
            "model": "claude-sonnet-4-6",
            "conversation": 1,
        },
    )
    _db.append_event(
        conn,
        project_root,
        feature,
        {
            "type": "PHASE_START",
            "feature": feature,
            "ts": "2026-01-01T00:00:01Z",
        },
    )

    calls = []
    monkeypatch.setattr(
        "pathly_orchestrator.otel_export._do_export",
        lambda event, endpoint: calls.append((event, endpoint)),
    )
    exit_exc = _run_cli(
        [
            "pathly-otel-export",
            "--feature",
            feature,
            "--endpoint",
            "http://localhost:4318",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert exit_exc.code == 0
    assert len(calls) == 1
