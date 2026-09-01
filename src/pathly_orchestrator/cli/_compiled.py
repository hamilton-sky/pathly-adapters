"""Second discovery source for the ``pathly-*`` CLI shortcuts: compiled-flow runs.

``_discovery.py`` finds work by globbing ``STATE.json`` off disk. A **compiled-flow** run
(``supervisor/compiled_flow.py``, FSM/DAG convergence Phase 2) keeps its position in the
flow in a local variable for the lifetime of the run — it writes no ``fsm_state`` row and
no ``STATE.json`` export, by design. So every disk glob misses it: ``pathly-status``
omitted such a run from the dashboard entirely, and ``pathly-log``/``back``/``ff``
answered ``Topic 'x' not found in any scan root``, which reads as "you typo'd the topic"
rather than the truth — "this run exists, and has no FSM state to show you".

The run IS recorded: ``registry._record_run_history`` writes one ``run_history`` row per
supervised run, keyed by the storage-dir SLUG, whose ``adapter`` column carries the FLOW
NAME (not a CLI adapter — see that function's docstring). A row whose flow is listed in
the ``flow.compiled_executors`` app-setting is a compiled-flow run. That is the whole
mechanism here.

**Only rows with no disk state matter.** A flow can be opted into the compiled executor
*after* it has FSM-driven history, so ``run_history`` holds rows for both. Callers merge
this source *behind* the disk scan and drop anything already found there, so an
FSM-backed topic is never described as stateless.

Every function fails safe to empty/``None``: these are human shortcuts that must keep
working in a cwd with no DB at all — the same contract ``_discovery.py``'s globs have.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn

_FIELDS = "id, feature, adapter, status, started_at, finished_at, stage_count, cost_usd, run_id"


def _epoch(row: dict) -> float:
    """Sort key comparable with ``Path.stat().st_mtime``, so compiled runs interleave with
    disk-discovered features by recency instead of being pinned to one end of the list.
    ``started_at``/``finished_at`` are written by two different call sites in two different
    ISO shapes (``…+00:00`` and ``…Z``); both parse once the ``Z`` is normalized."""
    raw = row.get("finished_at") or row.get("started_at") or ""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _project_root_keys(cwd: Path) -> list[str]:
    """The ``run_history.project_root`` spellings that mean *this* directory.

    Rows are written through ``db.queries.fsm_events._norm`` (forward slashes), and the
    writer may have been handed either the literal cwd or its resolved form, so match both.
    """
    candidates = [str(cwd)]
    try:
        candidates.append(str(cwd.resolve()))
    except OSError:
        pass
    keys: list[str] = []
    for cand in candidates:
        norm = cand.replace("\\", "/")
        if norm.startswith("//?/"):
            norm = norm[4:]
        if norm not in keys:
            keys.append(norm)
    return keys


def latest_compiled_runs(cwd: Path) -> list[dict]:
    """Newest compiled-flow run per topic for *cwd*, newest first.

    One entry per topic (not per run): the dashboard wants "where does this topic stand",
    and a re-run supersedes its predecessor. Each dict carries ``topic``, ``flow``,
    ``status``, ``stage_count``, ``cost_usd``, ``run_id`` and an ``mtime`` sort key.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.flow_settings import resolve_compiled_flows

        compiled = resolve_compiled_flows()
        if not compiled:
            return []
        keys = _project_root_keys(cwd)
        placeholders = ", ".join("?" for _ in keys)
        rows = (
            get_db()
            .execute(
                # nosec B608 - placeholders are generated from a bound list, values are bound
                f"SELECT {_FIELDS} FROM run_history "
                f"WHERE project_root IN ({placeholders}) ORDER BY id DESC",
                keys,
            )
            .fetchall()
        )
    except Exception:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for raw in rows:
        row = dict(raw)
        flow = row.get("adapter") or ""
        if flow not in compiled:
            continue
        # Legacy rows hold a full path in `feature` where new rows hold the bare slug
        # (see run_history._SLUG_MATCH); the basename is the topic either way.
        topic = str(row.get("feature") or "").rsplit("/", 1)[-1]
        if not topic or topic in seen:
            continue
        seen.add(topic)
        out.append(
            {
                "topic": topic,
                "flow": flow,
                "status": row.get("status") or "unknown",
                "stage_count": int(row.get("stage_count") or 0),
                "cost_usd": float(row.get("cost_usd") or 0.0),
                "run_id": row.get("run_id") or "",
                "mtime": _epoch(row),
                "compiled": True,
            }
        )
    return out


def find_compiled_run(cwd: Path, topic: str) -> dict | None:
    """The newest compiled-flow run named *topic* in *cwd*, or None."""
    for run in latest_compiled_runs(cwd):
        if run["topic"] == topic:
            return run
    return None


def describe_compiled_run(run: dict) -> list[str]:
    """Lines explaining a compiled-flow run — shared by ``log``/``back``/``ff`` so all
    three give the same account of why there is no FSM state to act on."""
    cost = run.get("cost_usd") or 0.0
    return [
        f"  {run['topic']} ran under the compiled-flow executor ({run['flow']}).",
        f"  Last run: {run['status']}  ·  {run['stage_count']} stage(s)  ·  ${cost:.2f}",
        f"  run_id: {run['run_id']}",
        "",
        "  A compiled-flow run holds its position in the flow in memory for the",
        "  lifetime of the run — it writes no FSM state and no event log, so there is",
        "  nothing here to show, roll back, or fast-forward. Use the Studio Monitor",
        "  (or GET /runs) for this run's stages, and `pathly-status` to see it listed.",
        "",
        "  To drive this topic through the FSM engine instead, remove its flow from the",
        "  `flow.compiled_executors` app-setting and start a fresh run.",
    ]


_SEP = "─" * 57


def _print_run(run: dict, headline: str) -> None:
    print(_SEP)
    print(headline)
    print(_SEP)
    for line in describe_compiled_run(run):
        print(line)
    print(_SEP)


def exit_topic_not_found(cwd: Path, topic: str, action: str) -> NoReturn:
    """Diagnose an unresolvable topic for ``log``/``back``/``ff``, then exit(1).

    "Not found in any scan root" is only true when nothing knows the topic. When it is a
    compiled-flow run, saying so sends the user hunting for a typo that isn't there.
    """
    run = find_compiled_run(cwd, topic)
    if run is None:
        print(f"Topic '{topic}' not found in any scan root.")
        sys.exit(1)
    _print_run(run, f"  No FSM state for {topic} — nothing to {action}.")
    sys.exit(1)


def exit_no_features(cwd: Path, action: str) -> NoReturn:
    """Same idea for the no-argument path: "No active features found" is a lie in a
    project whose only runs were compiled-flow ones."""
    runs = latest_compiled_runs(cwd)
    if not runs:
        print("No active features found.")
        sys.exit(1)
    _print_run(
        runs[0],
        f"  No FSM-backed feature to {action} — the most recent run is compiled.",
    )
    sys.exit(1)
