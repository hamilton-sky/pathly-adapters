"""Unified run read-model — _classify_kind / list_runs / get_run_detail / overlay_live_status
(unified-control-plane P0, ARCHITECTURE §1, §4, §8.1).

Covers the run-grain classifier (§1 table, incl. the accepted all-numeric-uuid edge), list_runs
folding stage rows out + including running rows + cost parity vs agent_invocations, get_run_detail
window joins (board posts run_id-vs-NULL with the out-of-window NULL post excluded, zero-post empty
list; a non-md artifact listed by metadata with NO hydrate; stages + per-stage run_log logs;
detail<->list parity; unknown run_id -> run None), and the supervisor dispatch overlay
(capabilities + live-status upgrade). Isolation via the _isolate_db autouse fixture in conftest.py.
"""

from __future__ import annotations

import sqlite3

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_history import upsert_run
from pathly_orchestrator.db.queries.run_history_read import (
    _classify_kind,
    get_run_detail,
    list_runs,
)
from pathly_orchestrator.db.queries.run_log import (
    update_run_log_stdout,
    write_run_log_spawn,
)
from pathly_orchestrator.supervisor.dispatch import overlay_live_status

# --- shared synthetic scenario -------------------------------------------------------------
PR = "C:/tmp/synthproj"
FEAT = "synthfeat"
PARENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"  # bare hex uuid + adapter=team -> flow
ST1 = "synthfeat-1-1784800000000"  # {topic}-{N}-{ts} -> stage
ST2 = "synthfeat-2-1784800000100"  # stage
SINGLE = "51ec1a2b-33cc-44dd-8eef-5566aabb7777"  # bare hex uuid -> single
# flow lifespan is the 30th 10:00 -> 10:05; the single run lives on the 28th (no overlap, so
# the flow's time-window cost sum never swallows the single's invocation).
T0 = "2026-07-30T10:00:00+00:00"
S1 = "2026-07-30T10:00:05+00:00"
S2 = "2026-07-30T10:00:10+00:00"
TF = "2026-07-30T10:05:00Z"
SG0 = "2026-07-28T08:00:00+00:00"
SGF = "2026-07-28T08:10:00Z"


def _ins(conn: sqlite3.Connection, sql: str, args: tuple) -> None:
    conn.execute(sql, args)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    """A flow parent + its two stages + a separate single run, with invocations, run_log
    rows, board posts (run_id-exact, NULL-in-window, NULL-out-of-window) and a non-md
    artifact — the fixture every read-model assertion below reads back."""
    upsert_run(conn, PR, FEAT, PARENT, "done", started_at=T0, finished_at=TF,
               stage_count=2, adapter="team", board_scope=FEAT)
    upsert_run(conn, PR, FEAT, ST1, "done", started_at=S1, finished_at=S1,
               adapter="claude", board_scope=FEAT)
    upsert_run(conn, PR, FEAT, ST2, "done", started_at=S2, finished_at=S2,
               adapter="claude", board_scope=FEAT)
    upsert_run(conn, PR, FEAT, SINGLE, "done", started_at=SG0, finished_at=SGF,
               adapter="claude", board_scope=FEAT)

    ai = ("INSERT INTO agent_invocations "
          "(project_root,feature,run_id,stage,started_at,tokens_in,tokens_out,cost_usd,board_scope) "
          "VALUES (?,?,?,?,?,?,?,?,?)")
    _ins(conn, ai, (PR, FEAT, ST1, "BUILDING", S1, 1000, 500, 0.10, FEAT))
    _ins(conn, ai, (PR, FEAT, ST2, "REVIEWING", S2, 2000, 800, 0.20, FEAT))
    _ins(conn, ai, (PR, FEAT, SINGLE, "BUILDING", SG0, 100, 50, 0.05, FEAT))

    write_run_log_spawn(conn, ST1, "BUILDING", "PROMPT build")
    update_run_log_stdout(conn, ST1, "stdout of build")
    write_run_log_spawn(conn, ST2, "REVIEWING", "PROMPT review")
    update_run_log_stdout(conn, ST2, "stdout of review")

    cm = ("INSERT INTO comms_messages "
          "(id,board,scope,from_agent,to_agent,type,text,ts,run_id) VALUES (?,?,?,?,?,?,?,?,?)")
    _ins(conn, cm, ("msg-exact", FEAT, FEAT, "builder", "*", "decision", "exact",
                    "2026-07-30T10:00:30+00:00", PARENT))
    _ins(conn, cm, ("msg-window", FEAT, FEAT, "reviewer", "*", "discovery", "window",
                    "2026-07-30T10:01:00+00:00", None))
    _ins(conn, cm, ("msg-outside", FEAT, FEAT, "x", "*", "note", "outside",
                    "2026-07-29T09:00:00+00:00", None))  # NULL run_id, before window -> excluded
    _ins(conn, "INSERT INTO comms_artifacts "
               "(id,message_id,path,type,title,summary,created_at) VALUES (?,?,?,?,?,?,?)",
         ("art-png", "msg-exact", "assets/diagram.png", "png", "diagram", None,
          "2026-07-30T10:00:31+00:00"))


# --- _classify_kind (ARCHITECTURE §1) ------------------------------------------------------
def test_classify_kind_matches_arch_section1() -> None:
    assert _classify_kind("sched-3f2a", "claude") == "loop"
    assert _classify_kind("synthfeat-1-1784800000000", "claude") == "stage"
    assert _classify_kind("t-2-1784800000100-q1", "claude") == "stage"  # retry -q
    assert _classify_kind("t-3-1784800000200-fb2", "claude") == "stage"  # retry -fb
    for flow_adapter in ("team", "team-build", "consultation",
                         "feature-consultation", "project-consultation"):
        assert _classify_kind(PARENT, flow_adapter) == "flow"
    assert _classify_kind(PARENT, "claude") == "single"
    assert _classify_kind(PARENT, None) == "single"
    # 'sched-' wins even when the tail is otherwise stage-shaped
    assert _classify_kind("sched-abc-1-1784800000000", "claude") == "loop"
    # accepted edge (§1/§1.1): an all-numeric-tail bare uuid reads as 'stage'
    assert _classify_kind("1111-2222-3333-4444-555566667777", "claude") == "stage"


# --- list_runs (ARCHITECTURE §4.1) ---------------------------------------------------------
def test_list_runs_folds_stages_and_reconciles_cost() -> None:
    conn = get_db()
    _seed(conn)
    byid = {r["run_id"]: r for r in list_runs(conn, PR, limit=20)}

    # stage rows are folded OUT of the top-level list
    assert ST1 not in byid and ST2 not in byid
    # flow parent: cost == SUM of its stage agent_invocations (parity §1.1, figures reconcile)
    assert byid[PARENT]["kind"] == "flow"
    assert byid[PARENT]["cost_usd"] == pytest.approx(0.30)
    assert byid[PARENT]["tokens_total"] == 1000 + 500 + 2000 + 800
    # single: cost identical to its own agent_invocations row (parity §1.1, same fact table)
    assert byid[SINGLE]["kind"] == "single"
    assert byid[SINGLE]["cost_usd"] == pytest.approx(0.05)
    assert byid[SINGLE]["tokens_total"] == 150
    # row shape
    assert {"run_id", "kind", "feature", "board_scope", "status", "adapter", "started_at",
            "finished_at", "stage_count", "cost_usd", "tokens_total"} <= set(byid[PARENT])


def test_list_runs_includes_running_rows() -> None:
    """A run still RUNNING appears (status from run_history) — Monitor RECENT cannot show it."""
    conn = get_db()
    upsert_run(conn, PR, FEAT, "run-live-0001", "running",
               started_at=T0, adapter="claude", board_scope=FEAT)
    live = [r for r in list_runs(conn, PR, limit=50) if r["status"] == "running"]
    assert any(r["run_id"] == "run-live-0001" for r in live)


def test_list_runs_empty_project_root_returns_empty() -> None:
    assert list_runs(get_db(), "", limit=10) == []


# --- get_run_detail (ARCHITECTURE §4.2-4.3) ------------------------------------------------
def test_get_run_detail_flow_stages_logs_board_and_parity() -> None:
    conn = get_db()
    _seed(conn)
    d = get_run_detail(conn, PARENT)

    assert d["run"]["kind"] == "flow"
    # stages: the two child stage rows, enriched with stage NAME + cost
    assert {s["run_id"] for s in d["stages"]} == {ST1, ST2}
    assert {s["stage"] for s in d["stages"]} == {"BUILDING", "REVIEWING"}
    assert sum(s["cost_usd"] for s in d["stages"]) == pytest.approx(0.30)
    # logs: one run_log row per stage, exactly the §4.2 keys
    assert {log["stdout"] for log in d["logs"]} == {"stdout of build", "stdout of review"}
    assert all(
        set(log) == {"stage", "prompt_sent", "board_context_injected", "stdin", "stdout", "ts"}
        for log in d["logs"]
    )
    # board posts: run_id-exact + NULL-in-window, in ts order; out-of-window NULL post excluded
    assert [b["id"] for b in d["board"]] == ["msg-exact", "msg-window"]
    assert "msg-outside" not in {b["id"] for b in d["board"]}
    # cost block + detail<->list parity
    assert d["cost"]["invocations"] == 2
    assert d["cost"]["cost_usd"] == pytest.approx(0.30)
    listed = {r["run_id"]: r for r in list_runs(conn, PR, 20)}[PARENT]
    assert d["cost"]["cost_usd"] == pytest.approx(listed["cost_usd"])


def test_get_run_detail_non_md_artifact_listed_without_hydrate() -> None:
    """A non-md artifact is returned by metadata only (path/type/title/summary) — no hydrate
    call, so nothing reads the file and there is no mojibake (AC-4)."""
    conn = get_db()
    _seed(conn)
    arts = get_run_detail(conn, PARENT)["artifacts"]
    assert len(arts) == 1
    assert set(arts[0]) == {"path", "type", "title", "summary"}
    assert arts[0]["type"] == "png" and arts[0]["path"].endswith("diagram.png")


def test_get_run_detail_single_zero_posts_empty_board() -> None:
    """A run with zero correlated posts -> empty Board tab, never an error (AC-3)."""
    conn = get_db()
    _seed(conn)
    d = get_run_detail(conn, SINGLE)
    assert d["run"]["kind"] == "single"
    assert d["board"] == []
    assert d["artifacts"] == []
    assert len(d["stages"]) == 1 and d["stages"][0]["run_id"] == SINGLE
    assert d["cost"]["cost_usd"] == pytest.approx(0.05)


def test_get_run_detail_unknown_run_id_returns_run_none() -> None:
    d = get_run_detail(get_db(), "does-not-exist")
    assert d["run"] is None
    assert d["stages"] == [] and d["board"] == [] and d["artifacts"] == []
    assert d["cost"] == {"cost_usd": 0.0, "tokens_total": 0, "invocations": 0}


# --- overlay_live_status (ARCHITECTURE §4.4) -----------------------------------------------
def test_overlay_attaches_capabilities_and_upgrades_running(monkeypatch) -> None:
    from types import SimpleNamespace

    from pathly_orchestrator.supervisor import registry as reg

    runs = [
        {"run_id": "r1", "kind": "flow", "status": "done"},
        {"run_id": "r2", "kind": "single", "status": "running"},
        {"run_id": "r3", "kind": "mystery", "status": "running"},
    ]
    # a live registry entry (keyed by topic, RunnerState-shaped) upgrades r2's persisted
    # 'running' to the live status; monkeypatch.setitem auto-reverts after the test.
    monkeypatch.setitem(reg._registry, "topicX", SimpleNamespace(run_id="r2", status="paused"))
    out = overlay_live_status(runs)

    assert out[0]["capabilities"] == ["abort"]
    assert out[1]["capabilities"] == ["abort"]
    assert out[2]["capabilities"] == []  # unknown kind -> no caps
    assert out[1]["status"] == "paused"  # upgraded from the live registry
    assert out[0]["status"] == "done"  # not 'running' -> untouched
    assert out[2]["status"] == "running"  # 'running' but no live match -> unchanged
