"""Project the AGENT_DONE event stream into agent_invocations (aggregate-on-read facts).

Why this exists
---------------
The real per-agent cost/tokens live in ``fsm_events`` — each agent writes an
``AGENT_DONE`` (self-reported cost) via the log-agent-done skill, and the stop hook
/ reconciliation window later appends a ``BILLING_UPDATE`` that *supersedes* it with
the provider-accurate figure. The DB-explorer roll-up and cost chart, however, read
``agent_invocations`` — which previously only captured supervised / board / editor
runs, written at spawn time with ``cost_usd=0``. So the bulk of real work
(interactive ``/pathly`` runs) never appeared, and even the rows that did were never
reconciled to their real cost.

This module makes ``agent_invocations`` a faithful projection of that event stream:
one row per ``AGENT_DONE``, keyed by its ``fsm_events.seq`` (``source_seq``), with the
superseding ``BILLING_UPDATE`` folded in (billing wins when priced — matching the
"supersedes for cost/token display" contract, so the 21 double-counted runs collapse
to one). Editor/chat one-shots (posted via ``/db/invocation``, feature ``"(project)"``,
no event) are a disjoint population with ``source_seq IS NULL`` and are left untouched.

Contracts
---------
* Idempotent: re-running ``backfill_invocations_from_events`` reproduces the same rows
  (upsert keyed by ``(project_root, feature, source_seq)``).
* Best-effort on the live path: ``on_event_appended`` never raises — telemetry must
  not break event append.
* Positional row access throughout — the connection's ``row_factory`` varies (the
  backfill runs during migrations before it is set).
"""

from __future__ import annotations

import json
import logging
import sqlite3

from ..connection import _get_write_lock

_log = logging.getLogger("pathly.telemetry")


def _num(v: object) -> float:
    try:
        return float(v or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _tier_for(conn: sqlite3.Connection, project_root: str, feature: str) -> str:
    """Best-effort board scope tier for (project_root, feature).

    AGENT_DONE events carry no scope tier, so we recover it from a sibling fact that
    does: a non-'feature' tier on any existing invocation or otel_span for this
    (project_root, feature). Defaults to 'feature' (correct for interactive runs).
    """
    for table in ("agent_invocations", "otel_spans"):
        try:
            row = conn.execute(
                f"SELECT scope_tier FROM {table} "
                "WHERE project_root=? AND feature=? AND scope_tier IS NOT NULL "
                "AND scope_tier!='feature' LIMIT 1",
                (project_root, feature),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except sqlite3.OperationalError:
            continue
    return "feature"


def _agent_done_rec(payload: dict) -> dict:
    """Build the invocation fields an AGENT_DONE payload can supply."""
    total_tok = int(_num(payload.get("total_tokens")))
    return {
        "agent_role": payload.get("agent") or "agent",
        "conversation": payload.get("conversation"),
        "cost_usd": _num(payload.get("cost_usd")),
        # AGENT_DONE only ever carries total_tokens (never an in/out split); park the
        # total in tokens_in so SUM(tokens_in+tokens_out) is the true total. A later
        # BILLING_UPDATE overwrites both with the real split.
        "tokens_in": int(_num(payload.get("tokens_in"))) or total_tok,
        "tokens_out": int(_num(payload.get("tokens_out"))),
        "tool_uses": int(_num(payload.get("tool_uses"))),
        "summary": (payload.get("summary") or payload.get("result") or "")[:2000],
        "provider": payload.get("model") or payload.get("adapter") or None,
        "ts": payload.get("ts") or "",
    }


def _upsert_projected(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    source_seq: int,
    rec: dict,
    scope_tier: str,
) -> None:
    """Insert-or-replace the projected invocation row keyed by (pr, feature, source_seq)."""
    cost = _num(rec.get("cost_usd"))
    cost_source = "provider_reported" if cost > 0 else "unpriced"
    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM agent_invocations "
            "WHERE project_root=? AND feature=? AND source_seq=?",
            (project_root, feature, source_seq),
        )
        conn.execute(
            "INSERT INTO agent_invocations "
            "(project_root, feature, run_id, stage, agent_role, started_at, finished_at, "
            " tokens_in, tokens_out, cost_usd, session_id, summary, scope_tier, "
            " provider, cost_source, source_seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                feature,
                None,
                rec.get("agent_role"),
                rec.get("agent_role"),
                rec.get("ts"),
                rec.get("ts"),
                int(rec.get("tokens_in") or 0),
                int(rec.get("tokens_out") or 0),
                cost,
                None,
                rec.get("summary"),
                scope_tier or "feature",
                rec.get("provider"),
                cost_source,
                source_seq,
            ),
        )
        conn.commit()


def _fold_billing(rec: dict, payload: dict) -> None:
    """Fold a superseding BILLING_UPDATE into the anchor AGENT_DONE record (in place).

    Billing wins when it carries data: a priced billing overrides the cost; a billing
    with a real token split overrides tokens_in/out.
    """
    b_cost = _num(payload.get("cost_usd"))
    if b_cost > 0:
        rec["cost_usd"] = b_cost
    b_in = int(_num(payload.get("tokens_in")))
    b_out = int(_num(payload.get("tokens_out")))
    if (b_in + b_out) > 0:
        rec["tokens_in"] = b_in
        rec["tokens_out"] = b_out
    else:
        b_total = int(_num(payload.get("total_tokens")))
        if b_total > 0 and int(rec.get("tokens_in") or 0) == 0:
            rec["tokens_in"] = b_total
    if payload.get("tool_uses") is not None:
        rec["tool_uses"] = int(_num(payload.get("tool_uses")))


# ─── One-time / on-startup backfill ──────────────────────────────────────────────


def backfill_invocations_from_events(
    conn: sqlite3.Connection, project_root: str | None = None
) -> dict:
    """Rebuild the event-backed slice of agent_invocations from fsm_events.

    Idempotent. For every (project_root, feature) that has AGENT_DONE events, deletes
    its projected rows (``source_seq IS NOT NULL``) and re-inserts one per AGENT_DONE
    with the superseding BILLING_UPDATE folded in. Rows with ``source_seq IS NULL``
    (editor/chat one-shots) are never touched. Returns ``{rows, features, cost_usd}``.
    """
    where = ""
    params: list = []
    if project_root:
        where = "WHERE project_root=?"
        params = [project_root]

    rows = conn.execute(
        "SELECT seq, project_root, feature, event_type, payload FROM fsm_events "
        f"{where}{' AND' if where else 'WHERE'} event_type IN ('AGENT_DONE','BILLING_UPDATE') "
        "ORDER BY seq ASC",
        params,
    ).fetchall()

    # Fold the event stream into one record per AGENT_DONE (keyed by its seq).
    records: dict[int, dict] = {}
    last_ad: dict[tuple, int] = {}
    touched: set[tuple] = set()
    for r in rows:
        seq, pr, feat, etype, raw = r[0], r[1], r[2], r[3], r[4]
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        key = (pr, feat, payload.get("agent"), payload.get("conversation"))
        if etype == "AGENT_DONE":
            rec = _agent_done_rec(payload)
            rec["_pr"], rec["_feat"] = pr, feat
            records[seq] = rec
            last_ad[key] = seq
            touched.add((pr, feat))
        else:  # BILLING_UPDATE supersedes the last AGENT_DONE of this key
            anchor = last_ad.get(key)
            if anchor is not None:
                _fold_billing(records[anchor], payload)
            else:
                rec = _agent_done_rec(payload)
                rec["_pr"], rec["_feat"] = pr, feat
                records[seq] = rec
                touched.add((pr, feat))

    # A "touched" feature is one with AGENT_DONE/BILLING_UPDATE events — the projected
    # rows below are its complete, authoritative fact set, so drop ALL of its existing
    # rows first (stale spawn-time provisional rows AND any prior projection). Rows for
    # event-less features (editor/chat one-shots under "(project)") are never in
    # `touched`, so they survive untouched.
    with _get_write_lock(conn):
        for pr, feat in touched:
            conn.execute(
                "DELETE FROM agent_invocations WHERE project_root=? AND feature=?",
                (pr, feat),
            )
        conn.commit()

    tier_cache: dict[tuple, str] = {}
    total_cost = 0.0
    for source_seq, rec in records.items():
        pr, feat = rec["_pr"], rec["_feat"]
        tk = (pr, feat)
        if tk not in tier_cache:
            tier_cache[tk] = _tier_for(conn, pr, feat)
        _upsert_projected(conn, pr, feat, source_seq, rec, tier_cache[tk])
        total_cost += _num(rec.get("cost_usd"))

    return {
        "rows": len(records),
        "features": len(touched),
        "cost_usd": round(total_cost, 4),
    }


# ─── Live write-path hook ─────────────────────────────────────────────────────────


def on_event_appended(
    conn: sqlite3.Connection,
    seq: int,
    project_root: str,
    feature: str,
    event_dict: dict,
) -> None:
    """Project a freshly-appended AGENT_DONE / BILLING_UPDATE into agent_invocations.

    Called from ``append_event`` for every event write — cheap and best-effort, it
    must never raise. AGENT_DONE upserts its own row; BILLING_UPDATE patches the row
    of the AGENT_DONE it supersedes (same project_root/feature/agent/conversation).
    """
    try:
        etype = event_dict.get("type") or event_dict.get("event_type")
        if etype == "AGENT_DONE":
            rec = _agent_done_rec(event_dict)
            _upsert_projected(
                conn,
                project_root,
                feature,
                seq,
                rec,
                _tier_for(conn, project_root, feature),
            )
        elif etype == "BILLING_UPDATE":
            anchor = conn.execute(
                "SELECT seq FROM fsm_events WHERE project_root=? AND feature=? "
                "AND event_type='AGENT_DONE' "
                "AND json_extract(payload,'$.agent') IS ? "
                "AND IFNULL(json_extract(payload,'$.conversation'),-1)=IFNULL(?,-1) "
                "AND seq<? ORDER BY seq DESC LIMIT 1",
                (
                    project_root,
                    feature,
                    event_dict.get("agent"),
                    event_dict.get("conversation"),
                    seq,
                ),
            ).fetchone()
            if anchor is None:
                # Orphan billing — a BILLING_UPDATE with no preceding AGENT_DONE for
                # this key (e.g. the reconciliation window fired for a run whose agent
                # never wrote AGENT_DONE). Record it as its own row keyed by the
                # billing's seq so the cost is captured, matching the backfill.
                rec = _agent_done_rec(event_dict)
                _upsert_projected(
                    conn,
                    project_root,
                    feature,
                    seq,
                    rec,
                    _tier_for(conn, project_root, feature),
                )
                return
            anchor_seq = anchor[0]
            row = conn.execute(
                "SELECT cost_usd, tokens_in, tokens_out FROM agent_invocations "
                "WHERE project_root=? AND feature=? AND source_seq=?",
                (project_root, feature, anchor_seq),
            ).fetchone()
            rec = {
                "cost_usd": _num(row[0]) if row else 0.0,
                "tokens_in": int(row[1]) if row and row[1] else 0,
                "tokens_out": int(row[2]) if row and row[2] else 0,
            }
            _fold_billing(rec, event_dict)
            with _get_write_lock(conn):
                cost = _num(rec.get("cost_usd"))
                conn.execute(
                    "UPDATE agent_invocations SET cost_usd=?, tokens_in=?, tokens_out=?, "
                    "cost_source=? WHERE project_root=? AND feature=? AND source_seq=?",
                    (
                        cost,
                        int(rec.get("tokens_in") or 0),
                        int(rec.get("tokens_out") or 0),
                        "provider_reported" if cost > 0 else "unpriced",
                        project_root,
                        feature,
                        anchor_seq,
                    ),
                )
                conn.commit()
    except Exception:  # noqa: BLE001 — best-effort; never break event append
        _log.debug("on_event_appended projection skipped", exc_info=True)
