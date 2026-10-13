"""Human escalation gate — an open gate addressed to a human blocks the transition.

The defect this closes: escalations fired correctly and then gated nothing. On the board in
docs/BOARD_LIFECYCLE_FINDINGS.md four messages sat ``status='pending'`` with
``acknowledged_by=[]`` — including "Human checkpoint required" and an evaluator warning that
Option B "is not recommended" and needed an explicit human answer — while the FSM ran
PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → DONE straight past all
four. Worse, the same role that raised a gate later dissolved it: the evaluator warned at
15:00 and adopted the thing it warned about at 17:20. Total human input on that run was one
sentence.

Two decisions shape this, both deliberate:

**Only ``to_agent='human'`` escalations gate.** Agent-addressed escalations are ordinary
feedback routing — the pipeline is built to resolve those itself, and gating on them would
wedge runs that today self-heal. The rule an agent can hold in its head is: raise it for a
human and it blocks; raise it for an agent and it routes.

**Pause, don't stall.** The run stops at the gate and reports it, and a human clears it one
of two ways: acknowledge the escalation (``POST /comms/acknowledge`` — the normal path, after
which the gate is simply gone), or force past it explicitly. Forcing is recorded on the board
as a ``decision`` naming every gate it skipped, so a bypassed gate stays auditable instead of
becoming invisible. A hard stall with no override was the alternative; it is the stronger
safety property but kills an overnight headless run at the first checkpoint, losing all of its
progress.

The override is reachable ONLY by a caller that passes ``force_past_gate`` — it is a human
affordance. Nothing in an agent's prompt or fragment mentions it, because an agent that can
force past a human gate is precisely the failure this module exists to prevent.
"""

from __future__ import annotations

import logging

from pathly_orchestrator.db.provenance_values import SYSTEM_ROLE

_log = logging.getLogger("pathly.fsm")

# The escalation must be addressed to a human to gate. "*" (broadcast) does NOT gate — it is
# the default `to` on every post, so treating it as human-addressed would make every
# broadcast escalation a checkpoint.
_HUMAN_TARGETS = ("human",)


def gate_scopes(
    topic: str, scope: str, project_root: str, goal_id: str = ""
) -> list[str]:
    """The scopes a run's human escalations can sit on: its own, plus its parent board's.

    A goal run's topic (and the ``scope`` the supervisor sends) is its own storage slug,
    ``features/<f>/goals/<slug>``, while its agents post on the parent feature board, ``<f>``.
    Checking only the topic scope made the gate silently a no-op for every goal run.
    """
    scopes = [scope]
    try:
        from pathlib import PurePosixPath

        from pathly_orchestrator.fsm_compose import resolve_board_scope

        slug = PurePosixPath(str(topic).replace("\\", "/")).name or scope
        scopes.append(resolve_board_scope(slug, project_root, goal_id or ""))
    except Exception:
        _log.debug("gate_scopes: board scope unresolved", exc_info=True)
    return [s for s in dict.fromkeys(scopes) if s]


def open_human_gates(board: str, scope: str | list[str]) -> list[dict]:
    """Return unacknowledged escalations addressed to a human for this board/scope(s).

    Never raises: a DB hiccup must not wedge the pipeline, so it fails OPEN (returns []) —
    the same choice ``run_gates`` makes for ``require_tasks_done``. A gate that cannot be
    read is reported as absent rather than blocking every transition in the product.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import get_active_escalations

        scopes = [scope] if isinstance(scope, str) else list(scope)
        rows = get_active_escalations(
            get_db(), boards=[board or "feature"], scopes=scopes
        )
    except Exception:
        _log.debug("open_human_gates read failed — failing open", exc_info=True)
        return []

    gates: list[dict] = []
    for row in rows:
        if str(row.get("to_agent") or "").strip().lower() not in _HUMAN_TARGETS:
            continue
        # A row the server wrote itself (the park notice for a headless human checkpoint, a
        # task out of retries) announces a checkpoint the engine already enforces through a
        # feedback file or require_tasks_done. Gating on it too double-gates: a resumed parked
        # run would meet the escalation its own park posted and park again. The role comes
        # from the provenance stamp, which a request body cannot set.
        if row.get("author_role") == SYSTEM_ROLE:
            continue
        # acknowledged_by is JSON text; a non-empty list means a human has seen it. The
        # status='pending' filter upstream already implies this, but an acknowledge that
        # failed to flip status must not leave a permanently-stuck gate.
        ack = row.get("acknowledged_by") or "[]"
        if isinstance(ack, str) and ack.strip() not in ("", "[]", "null"):
            continue
        gates.append(
            {
                "id": row.get("id"),
                "text": (row.get("text") or "")[:400],
                "from": row.get("from_agent"),
                "scope": row.get("scope"),
                "ts": row.get("ts"),
            }
        )
    return gates


def record_gate_override(
    board: str, scope: str, gates: list[dict], actor: str = "human"
) -> None:
    """Post a board `decision` naming every gate a force-advance skipped, then acknowledge them.

    Without the decision the override is invisible and the board looks exactly like the
    un-gated behaviour this module replaced. The acknowledgement is what makes one force
    enough: a forced-past escalation left pending re-blocked every later transition, and each
    re-force posted another override. Best-effort — failing to record must not block the
    advance the human explicitly asked for.
    """
    if not gates:
        return
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import (
            acknowledge_message,
            post_message,
        )
        from pathly_orchestrator.runner.provenance import system_stamp

        # One override per board scope a gate sat on: a goal run's gates can sit on the parent
        # feature board, where a note on the run's own topic scope would never be read.
        by_scope: dict[str, list[dict]] = {}
        for g in gates:
            by_scope.setdefault(g.get("scope") or scope, []).append(g)
        for gate_scope, scoped in by_scope.items():
            listed = "; ".join(f"{g['text'][:80]} [{g['id']}]" for g in scoped)
            post_message(
                get_db(),
                board=board or "feature",
                scope=gate_scope,
                from_agent=actor,
                type="decision",
                text=(
                    f"GATE OVERRIDE — advanced past {len(scoped)} unacknowledged human "
                    f"escalation(s) without answering them: {listed}"
                ),
                # The server writes this row; the caller's identity is not known here.
                **system_stamp(),
            )
        for g in gates:
            acknowledge_message(
                get_db(), message_id=g["id"], agent=f"{actor} (gate override)"
            )
    except Exception:
        _log.debug("record_gate_override failed", exc_info=True)
