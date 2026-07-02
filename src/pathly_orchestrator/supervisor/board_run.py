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
    interactive: bool = False,
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
        interactive=interactive,
    )
    # telemetry-three-tier: a board/single run registers no topic RunnerState, so
    # api_lifecycle won't record it — the executor owns the projection. One agent
    # drains the whole goal, so a fresh trace with this single span as its root.
    from pathly_orchestrator.runner.telemetry import new_trace_id, scope_tier_for

    state.executor_owned_telemetry = True
    state.scope_tier = scope_tier_for(board)
    state.goal_trace_id = new_trace_id()
    # Interactive: spawn the bare REPL and let terminal.ts inject the prompt once the
    # '> ' readline prompt is ready (it stays open for further instructions).
    # Headless: the prompt is delivered via -p argv and the agent exits when done.
    return _run_stage_via_terminal(state, prompt, adapter, model, run_id, broadcast_fn)


def _compose_skill_body(skill: str, adapter: str, caps: dict | None = None) -> str:
    """Compose the chosen skill into its full prompt body (runner-mode delivery —
    assembled in Python and injected via argv; the CLI reads nothing from disk).
    Returns '' on any failure so a board run is never blocked by a bad skill name."""
    if not skill:
        return ""
    try:
        from pathly_orchestrator.skills.compose import compose_skill

        return compose_skill(skill, caps if caps is not None else (adapter or "claude"))
    except Exception:
        return ""


def _safe_call(fn: Callable, *args) -> None:
    """Invoke a lifecycle callback best-effort; a bad callback never breaks a run."""
    try:
        fn(*args)
    except Exception:
        pass


# How chatty the headless agent is on the board, chosen per-run from the Studio
# run modal. Only the cadence sentence changes — the POST mechanics below it are
# identical for every level. Unknown values fall back to "normal".
_PROGRESS_CADENCE = {
    "quiet": (
        "Post exactly TWO updates: (1) a one-line note when you START (what you "
        "are about to do), and (2) your final RESULT when done. Do NOT post "
        "intermediate progress."
    ),
    "normal": (
        "Post (1) a short note when you START (what you are about to do), (2) a "
        "line at each KEY STEP or finding, and (3) your final RESULT when done."
    ),
    "verbose": (
        "Post frequently so the human can follow every move: (1) a note when you "
        "START, (2) a line for EACH step — every file you read or write, every "
        "command you run, every finding — and (3) your final RESULT when done."
    ),
}


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
    system_prompt: str = "",
    interactive: bool = False,
    progress: str = "normal",
    storage_path: str = "",
    caps: dict | None = None,
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
    progress:
        How chatty the headless agent is on the board — "quiet" (start + result
        only), "normal" (start + key steps + result), or "verbose" (a line per
        step). Unknown values fall back to "normal".
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

    # Scope-aware board context (governance + memory across the user's selected
    # Reads tiers) — same source the FSM/team path uses, so single-agent and
    # /comms/run agents are no longer blind to the board. Honors the Reads toggle.
    from pathly_orchestrator.runner.comms_context import board_context_for

    context = board_context_for(board, scope, project_root or "", instructions or "")
    prompt_parts: list[str] = []
    # The composed skill body is the agent's behavior contract for this run.
    skill_body = _compose_skill_body(skill, adapter, caps=caps)
    if skill_body:
        prompt_parts.append(skill_body)
    if system_prompt:
        prompt_parts.append("## System instructions\n\n" + system_prompt.strip())
    if agent:
        prompt_parts.append(f"You are acting as the **{agent}** agent for this board.")
    if instructions:
        prompt_parts.append("## Task\n\n" + instructions.strip())
    # The board IS the conversation: the task is the latest human message; reply there.
    # This run is headless — the terminal does not stream — so the agent must narrate
    # its progress to the board or the human is blind. These POSTs are how the human
    # follows along; they are not a user-facing skill.
    _from = agent or "agent"
    cadence = _PROGRESS_CADENCE.get(progress, _PROGRESS_CADENCE["normal"])
    # Where the agent should write files: prefer the resolved storage_path when supplied
    # (goal-tier runs pass this); fall back to the feature inline-resolve for feature boards.
    if storage_path:
        where_line = f"Your working directory is: {storage_path}"
    elif board == "feature" and project_root:
        # feature inline fallback — route through the shared resolver so it finds the flat
        # home (pathly/features/<scope>/) first. The old inline probe checked pathly/<scope>
        # then legacy pathly/plans/<scope> and NEVER pathly/features/<scope>, so it missed
        # every current feature dir.
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        feature_path = _resolve_storage_path(None, project_root, scope)
        where_line = f"Your working directory is: {feature_path}"
    else:
        where_line = ""
    prompt_parts.append(
        "## Working from the board\n\n"
        "Your task is the most recent message from the human on this board (shown in "
        "the context below). Carry it out.\n\n"
        "IMPORTANT — this run is headless, so the human CANNOT see your terminal. Keep "
        "them in the loop by posting brief progress to the board as you go. POST to "
        "http://127.0.0.1:8765/comms/post with a JSON body:\n"
        f'  {{"feature": "{scope}", "from": "{_from}", "board": "{board}", "scope": "{scope}", '
        '"type": "status", "text": "<one or two sentences>"}\n'
        f"{cadence} Keep each post to one or two sentences — the board is the human's "
        "window into this run.\n\n"
        f"{where_line + chr(10) + chr(10) if where_line else ''}"
        "If you CREATE A FILE (an artifact), post it as an artifact AND link the path so the "
        "human can open it from the board. Provide TWO fields: text = a real 1-2 sentence "
        "description (what it is and why it matters, NOT a bare label); summary = a topic map of "
        "the file's sections (one line per heading) — this is the catalog entry other agents scan "
        "and is embedded for semantic retrieval. Include artifact_path and artifact_type:\n"
        f'  {{"feature": "{scope}", "from": "{_from}", "board": "{board}", "scope": "{scope}", '
        '"type": "artifact", "text": "<1-2 sentence description>", '
        '"summary": "<topic map of the file sections, one line per heading>", '
        '"artifact_path": "<relative or absolute path to the file you wrote>", '
        '"artifact_type": "md"}'
    )
    if context:
        prompt_parts.append(context)
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
                interactive=interactive,
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

    def _runner() -> None:
        # Async failure must still reach the board (so the human isn't blind) — the
        # lock is already freed by _work's finally; surface the error via on_done.
        try:
            _work()
        except Exception as exc:  # noqa: BLE001
            import logging

            # Log the traceback so the failure is visible in the FSM console, not just
            # swallowed into on_done (which a caller may choose to drop).
            logging.getLogger(__name__).exception("board run %s failed", run_id)
            if on_done is not None:
                _safe_call(
                    on_done, run_id, {"result": f"error: {exc}", "error": str(exc)}
                )

    # Async path (production): spawn the agent in the background and return at once
    # so the Start button never hangs; progress streams onto the board.
    threading.Thread(
        target=_runner, daemon=True, name=f"board-run-{run_id[:8]}"
    ).start()
    return {"ok": True, "run_id": run_id, "mode": mode, "status": "started"}
