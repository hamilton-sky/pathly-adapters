"""Cost reconciliation against ccusage — Pathly <= ccusage, per local day per tool.

ccusage measures every session on the machine from the CLIs' own transcripts, independently of
Pathly's parsers and rate table. Pathly reporting MORE than that for a day is impossible unless a
Pathly parser or rate is wrong; that is the one thing this check flags.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import date

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.cost_by_tool import daily_cost_by_tool
from pathly_orchestrator.db.queries.invocations import write_agent_invocation
from pathly_orchestrator.runner.ccusage import (
    ccusage_daily,
    parse_ccusage_daily,
    tool_for_model,
)
from pathly_orchestrator.runner.cost_reconcile import compare_day, reconcile_costs

PR = "C:/reconcile-proj"
DAY = date(2026, 10, 10)

# Shape measured from ccusage 20.x (`ccusage daily --json`): codex rides inside `daily`,
# split per model in modelBreakdowns, keyed by `period`.
CCUSAGE_JSON = {
    "daily": [
        {
            "period": "2026-10-10",
            "totalCost": 12.5,
            "modelBreakdowns": [
                {"modelName": "claude-sonnet-4-6", "cost": 10.0},
                {"modelName": "gpt-5.5", "cost": 2.0},
                {"modelName": "claude-haiku-4-5", "costUSD": 0.5},
            ],
        },
        {"date": "2026-10-09", "totalCost": 3.0, "metadata": {"agents": ["codex"]}},
    ]
}


def _row(cost, provider, ts="2026-10-10T12:00:00Z", source="provider_reported"):
    write_agent_invocation(
        get_db(),
        PR,
        "feat",
        {
            "started_at": ts,
            "finished_at": ts,
            "cost_usd": cost,
            "provider": provider,
            "cost_source": source,
            "agent_role": "builder",
        },
    )


# ── ccusage parsing ──────────────────────────────────────────────────────────────


def test_parse_splits_by_tool_with_cost_key_aliases():
    out = parse_ccusage_daily(CCUSAGE_JSON)
    assert out["2026-10-10"] == {"claude": 10.5, "codex": 2.0}
    # No modelBreakdowns → the whole day under a coarse label, never dropped.
    assert out["2026-10-09"] == {"unattributed": 3.0}


def test_parse_rejects_unknown_shape_naming_keys_only():
    with pytest.raises(ValueError, match="secret_key"):
        parse_ccusage_daily({"secret_key": "do-not-leak-this-value"})


def test_tool_for_model_uses_pathly_vocabulary():
    assert tool_for_model("claude-opus-4-5") == "claude"
    assert tool_for_model("gpt-5-codex") == "codex"
    assert tool_for_model("Mystery-Model") == "mystery-model"


def test_ccusage_daily_none_when_not_installed(monkeypatch):
    monkeypatch.setenv("PATHLY_CCUSAGE_BIN", "/nonexistent/ccusage")
    assert ccusage_daily(DAY, DAY) is None


def test_ccusage_daily_runs_binary_with_offline_local_range(tmp_path, monkeypatch):
    argv_log = tmp_path / "argv.json"
    fake = tmp_path / "ccusage"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"json.dump(sys.argv[1:], open({str(argv_log)!r}, 'w'))\n"
        f"print(json.dumps({CCUSAGE_JSON!r}))\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATHLY_CCUSAGE_BIN", str(fake))
    if os.name == "nt":
        pytest.skip("shebang script")
    out = ccusage_daily(date(2026, 10, 4), DAY)
    assert out is not None and out["2026-10-10"]["codex"] == 2.0
    assert json.loads(argv_log.read_text()) == [
        "daily",
        "--json",
        "--offline",
        "--since",
        "20261004",
        "--until",
        "20261010",
    ]


def test_ccusage_daily_none_on_failure_exit(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("shebang script")
    fake = tmp_path / "ccusage"
    fake.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(3)\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATHLY_CCUSAGE_BIN", str(fake))
    assert ccusage_daily(DAY, DAY) is None


# ── Pathly side ──────────────────────────────────────────────────────────────────


def test_daily_cost_by_tool_buckets_model_and_adapter_slug_providers():
    _row(1.0, "claude-sonnet-4-6")
    _row(0.5, "gpt-5-codex", source="estimated")
    _row(0.25, "codex", source="estimated")  # one-shot: adapter slug, no model
    _row(9.0, "claude-sonnet-4-6", ts="2026-09-01T12:00:00Z")  # outside range
    out = daily_cost_by_tool(get_db(), "2026-10-10", "2026-10-10")
    assert out["2026-10-10"]["claude"] == {"usd": 1.0, "estimated_usd": 0.0, "rows": 1}
    assert out["2026-10-10"]["codex"]["usd"] == pytest.approx(0.75)
    assert out["2026-10-10"]["codex"]["estimated_usd"] == pytest.approx(0.75)
    assert out["2026-10-10"]["codex"]["rows"] == 2


# ── comparison ───────────────────────────────────────────────────────────────────


def test_compare_flags_only_pathly_exceeding_ccusage():
    rows = {
        r["tool"]: r
        for r in compare_day(
            {
                "claude": {"usd": 4.0},  # 40% of machine spend — fine
                "codex": {"usd": 3.0, "estimated_usd": 3.0},  # > 2.0 machine total
                "gemini": {"usd": 1.0},  # ccusage doesn't measure it
            },
            {"claude": 10.0, "codex": 2.0},
        )
    }
    assert rows["claude"]["status"] == "ok" and rows["claude"]["coverage"] == 0.4
    assert rows["codex"]["status"] == "overstated"
    assert rows["gemini"]["status"] == "not_covered"


def test_compare_tolerance_absorbs_small_drift():
    (row,) = compare_day({"codex": {"usd": 2.15}}, {"codex": 2.0}, tolerance=0.10)
    assert row["status"] == "ok"
    (row,) = compare_day({"codex": {"usd": 2.25}}, {"codex": 2.0}, tolerance=0.10)
    assert row["status"] == "overstated"


def test_pathly_spend_with_no_ccusage_spend_is_overstated():
    (row,) = compare_day({"claude": {"usd": 1.0}}, {})
    assert row["status"] == "overstated" and row["coverage"] is None


# ── end to end ───────────────────────────────────────────────────────────────────


def test_reconcile_reports_overstated_day():
    _row(1.0, "claude-sonnet-4-6")
    _row(5.0, "gpt-5-codex", source="estimated")
    report = reconcile_costs(
        get_db(),
        days=2,
        today=DAY,
        ccusage_fn=lambda s, u: parse_ccusage_daily(CCUSAGE_JSON),
    )
    assert report["since"] == "2026-10-09" and report["until"] == "2026-10-10"
    assert report["status"] == "overstated"
    assert report["overstated"] == ["2026-10-10:codex"]
    assert [d["date"] for d in report["days"]] == ["2026-10-09", "2026-10-10"]


def test_reconcile_unavailable_without_ccusage():
    report = reconcile_costs(get_db(), days=1, today=DAY, ccusage_fn=lambda s, u: None)
    assert report["status"] == "unavailable" and report["days"] == []


def test_reconcile_endpoint(monkeypatch):
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.runner import ccusage as ccusage_mod

    _row(1.0, "claude-sonnet-4-6", ts=f"{date.today().isoformat()}T12:00:00Z")
    today = date.today().isoformat()
    monkeypatch.setattr(
        ccusage_mod,
        "ccusage_daily",
        lambda s, u: {today: {"claude": 4.0}},
    )
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.get("/telemetry/reconcile?days=1&project_root=C:\\reconcile-proj")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["project_root"] == "C:/reconcile-proj"
    (claude,) = body["days"][0]["tools"]
    assert claude["coverage"] == 0.25
