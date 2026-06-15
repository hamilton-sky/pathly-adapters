"""Single-agent board run — BOARD-RUNTIME-SPEC §2 / US4.

start_board_run acquires the board run-lock (A2/D1), assembles board context,
and invokes spawn_fn with the combined prompt.  spawn_fn is dependency-injected
so tests can pass a fake without touching the real PTY machinery.
"""
from __future__ import annotations

import threading
import uuid
from typing import Callable, Optional


def _format_board_info(
    decisions: list[dict],
    escalations: list[dict],
    recent: list[dict],
) -> str:
    """Build a compact markdown board-info block from raw DB rows.

    Two sections:
      ### Governance  — pending decisions + open escalations (deterministic)
      ### Recent context — latest messages on the board (up to 20)
    Returns '' when all three lists are empty.
    """
    if not decisions and not escalations and not recent:
        return ""

    lines: list[str] = ["## Board Context", ""]

    if decisions or escalations:
        lines.append("### Governance")
        lines.append("")
        if decisions:
            lines.append("**Pending decisions:**")
            for msg in decisions:
                text = msg.get("text", "")
                tier = msg.get("board", "feature")
                lines.append(f"  • [{tier}] {text}")
        if escalations:
            lines.append("**Open escalations:**")
            for msg in escalations:
                text = msg.get("text", "")
                tier = msg.get("board", "feature")
                lines.append(f"  • [{tier}] {text}")
        lines.append("")

    if recent:
        lines.append("### Recent context")
        lines.append("")
        for msg in recent:
            from_agent = msg.get("from_agent", "?")
            msg_type = msg.get("type", "")
            text = msg.get("text", "")
            lines.append(f"  • [{from_agent}/{msg_type}] {text}")

    return "\n".join(lines) + "\n"


def _default_spawn(
    *,
    board: str,
    scope: str,
    mode: str,
    prompt: str,
    run_id: str,
    project_root: str,
    model: str,
    adapter: str,
    broadcast_fn=None,
) -> dict:
    """Default spawn_fn: thin wrapper around supervisor.terminal._run_stage_via_terminal.

    Imported lazily so import of board_run never pulls in the full supervisor stack
    (important for test isolation and to keep layer boundaries clean).

    A board run is a one-shot single agent — not part of a flow — so we build a
    minimal headless RunnerState and hand it to the existing stage runner, whose
    signature is (state, instructions, adapter, model, run_id, broadcast_fn, ...).
    """
    from pathly_orchestrator.supervisor.state import RunnerState
    from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

    state = RunnerState(
        topic=scope,
        flow="board-run",
        project_root=project_root,
        model=model,
        timeout=600,
        run_id=run_id,
        current_state=(mode or "board-run"),
        current_adapter=adapter,
        interactive=False,
    )
    return _run_stage_via_terminal(state, prompt, adapter, model, run_id, broadcast_fn)


def _compose_skill_body(skill: str, adapter: str) -> str:
    """Compose the chosen skill into its full prompt body (runner-mode delivery —
    assembled in Python and injected via argv; the CLI reads nothing from disk).
    Returns '' on any failure so a board run is never blocked by a bad skill name."""
    if not skill:
        return ""
    try:
        from pathly_orchestrator.skills.compose import compose_skill
        return compose_skill(skill, adapter or "claude")
    except Exception:
        return ""


def _safe_call(fn: Callable, *args) -> None:
    """Invoke a lifecycle callback best-effort; a bad callback never breaks a run."""
    try:
        fn(*args)
    except Exception:
        pass


def start_board_run(
    board: str,
    scope: str,
    mode: str,
    instructions: str = "",
    *,
    project_root: str = "",
    model: str = "claude-sonnet-4-6",
    adapter: str = "claude",
    agent: str = "",
    skill: str = "",
    broadcast_fn=None,
    spawn_fn: Callable | None = None,
    on_start: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    block: bool = False,
) -> dict:
    """Acquire the board lock and spawn a single-agent run.

    Parameters
    ----------
    board:
        Board tier — "feature", "project", or "global".
    scope:
        Board scope identifier (e.g. feature name, project root, "global").
    mode:
        Run mode string — "single-agent" or "evaluator".
    instructions:
        Optional extra instructions prepended to the board context.
    project_root:
        Filesystem root used for artefact paths and DB lookup.
    model:
        Model ID passed to the spawn function.
    adapter:
        Adapter name (e.g. "claude").
    broadcast_fn:
        Optional SSE broadcast callable; forwarded to spawn_fn.
    spawn_fn:
        Injectable spawn callable.  When None the real terminal stage runner is
        used.  In tests pass a fake that records its arguments.

    Returns
    -------
    dict
        ``{"ok": True, "run_id": ..., "mode": ..., "result": ...}``
        or ``{"ok": False, "error": "board_busy", "holder": <run_id>}`` when the
        board is already locked.
    """
    from pathly_orchestrator.supervisor import board_lock

    run_id = str(uuid.uuid4())

    # Lock is acquired synchronously so the caller can answer 409 immediately.
    if not board_lock.acquire(board, scope, run_id):
        return {
            "ok": False,
            "error": "board_busy",
            "holder": board_lock.holder(board, scope),
        }

    # Evaluator mode defaults to the evaluator agent + evaluate skill (E1/E2).
    if mode == "evaluator":
        agent = agent or "evaluator"
        skill = skill or "planning/evaluate"

    context = _build_context(board=board, scope=scope)
    prompt_parts: list[str] = []
    # The composed skill body is the agent's behavior contract for this run.
    skill_body = _compose_skill_body(skill, adapter)
    if skill_body:
        prompt_parts.append(skill_body)
    if agent:
        prompt_parts.append(f"You are acting as the **{agent}** agent for this board.")
    if instructions:
        prompt_parts.append("## Task\n\n" + instructions.strip())
    if context:
        prompt_parts.append(context)
    # Keep the human in the loop — the board must not go dark during the run.
    prompt_parts.append(
        "When you finish, post a short status summary of what you did to this board "
        "(POST http://127.0.0.1:8765/comms/post with type=status) so the human can "
        "see the outcome without reading your terminal."
    )
    prompt = "\n\n".join(prompt_parts)

    effective_spawn = spawn_fn if spawn_fn is not None else _default_spawn

    def _work() -> dict:
        # on_start / on_done let the caller (HTTP layer) post lifecycle messages to
        # the board without board_run importing http_server (layer rule).
        try:
            if on_start is not None:
                _safe_call(on_start, run_id)
            result = effective_spawn(
                board=board,
                scope=scope,
                mode=mode,
                prompt=prompt,
                run_id=run_id,
                project_root=project_root,
                model=model,
                adapter=adapter,
                broadcast_fn=broadcast_fn,
            )
            if on_done is not None:
                _safe_call(on_done, run_id, result)
            return result if isinstance(result, dict) else {"result": result}
        finally:
            board_lock.release(board, scope, run_id)

    if block:
        # Synchronous path — used by tests so they can assert on the result.
        result = _work()
        return {"ok": True, "run_id": run_id, "mode": mode, "result": result}

    # Async path (production): spawn the agent in the background and return at once
    # so the Start button never hangs; progress streams onto the board.
    threading.Thread(target=_work, daemon=True, name=f"board-run-{run_id[:8]}").start()
    return {"ok": True, "run_id": run_id, "mode": mode, "status": "started"}


def _build_context(*, board: str, scope: str) -> str:
    """Fetch governance + recent messages for (board, scope) and format them."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import (
            get_active_escalations,
            get_messages,
            get_pending_decisions,
        )

        conn = get_db()
        decisions = get_pending_decisions(conn, boards=[board], scopes=[scope])
        escalations = get_active_escalations(conn, boards=[board], scopes=[scope])
        recent = get_messages(conn, board=board, scope=scope, limit=20)
    except Exception:
        decisions = []
        escalations = []
        recent = []

    return _format_board_info(decisions, escalations, recent)
