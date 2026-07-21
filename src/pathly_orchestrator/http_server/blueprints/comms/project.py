"""Project decompose endpoint (/comms/project/decompose).

Project-planner one altitude above ``features.py``: it splits a big spec dropped
on the PROJECT board into 2-5 sibling FEATURE cards (each scaffolded under
``pathly/features/<slug>/``). Mirrors ``/comms/features/decompose`` — same rigor
ladder (light | full | consultation), the terminal emit is ``type=feature`` (not
``type=goal``) and the heavy tier runs the ``project-consultation`` flow.

The project board's canonical scope is the NORMALIZED project_root path
(``_project_scope``) — the literal ``"project"`` is only the no-root fallback and Studio's
board KEY, never a real scope. The consultation keys its feature-count gate AND its board
posts by that root scope; ``fsm_compose`` normalizes the stage's ``board_scope`` to the same
root (a project run's storage basename is ``project``, which must NOT leak as the post
scope) so agent posts land where the board reads them. Storage is the fixed
``pathly/project/`` dir (decoupled from the path-like topic).
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("comms_project", __name__)

_VALID_RIGORS = {"light", "full", "consultation"}
_DEFAULT_MODEL = "claude-sonnet-4-6"
# Fallback PROJECT-board scope, used ONLY when no project_root is supplied. The
# CANONICAL scope is the NORMALIZED project_root path — that is what Studio
# (commsApi.ts) and comms_context injection both key the project board by, so
# feature cards posted there are visible to the UI and injectable as siblings.
_PROJECT_SCOPE = "project"


def _project_scope(project_root: str, override: str = "") -> str:
    """Resolve the project-board scope key: an explicit override, else the
    normalized project_root path (``\\`` → ``/``, no trailing slash), else the
    literal fallback. Mirrors goal_executor's ``project_root or "project"``."""
    # 'project' is the literal fallback AND the Studio project-board KEY — never a real
    # scope override. Treat it as absent so the scope falls to the normalized project_root
    # (what the board + comms_context key by); otherwise the consultation's features and
    # lifecycle posts land at scope='project', invisible on the per-project-root board.
    if override and override != _PROJECT_SCOPE:
        return override
    norm = (project_root or "").replace("\\", "/").rstrip("/")
    return norm or _PROJECT_SCOPE


@bp.route("/comms/project/decompose", methods=["POST"])
def comms_project_decompose():
    """Decompose a big project spec into sibling FEATURE cards.

    Body: {project?, project_root, rigor, adapter?, model?}
    rigor: "light" | "full"  → planning/project-decompose (single-agent board run)
           "consultation"     → project-consultation FSM flow (PO→…→project-decompose)
    ``project`` overrides the project-board scope; by default the scope is the
    normalized ``project_root`` path (what Studio + comms_context injection use).
    """
    try:
        # silent=True: a missing/invalid body returns a clean 400, never a 500
        # (T3 contract: best-effort, never 500 on a malformed/absent request).
        data = request.get_json(silent=True)
        if not data:
            return (
                jsonify({"error": "Missing JSON body", "reason": "missing_body"}),
                400,
            )

        rigor = (data.get("rigor") or "light").strip().lower()
        if rigor not in _VALID_RIGORS:
            return (
                jsonify(
                    {
                        "error": (
                            f"Field 'rigor' must be one of: {', '.join(sorted(_VALID_RIGORS))}"
                        ),
                        "reason": "invalid_rigor",
                    }
                ),
                400,
            )

        project_root = (data.get("project_root") or "").strip()
        adapter = (data.get("adapter") or "claude").strip()
        model = (data.get("model") or "").strip()

        # Flow-gate-preview (P3): transient per-stage prompt overrides for the consultation
        # FSM flow only — the light/full single-agent dispatch below uses prompt_override,
        # never stage_overrides.
        from ..runner._runner_bp import _validate_stage_overrides

        stage_overrides = _validate_stage_overrides(
            data.get("stage_overrides"), "project-consultation", project_root
        )

        board = "project"
        # Canonical scope = normalized project_root (Studio + comms_context injection
        # agree on this). An explicit `project` overrides; "project" is the no-root
        # fallback. Posting features at this scope is what makes them injectable as
        # siblings into the next feature's decompose prompt (T4 sibling-awareness).
        scope = _project_scope(project_root, (data.get("project") or "").strip())
        project = scope

        if rigor in ("light", "full"):
            return _dispatch_board_run(
                project=project,
                board=board,
                scope=scope,
                rigor=rigor,
                project_root=project_root,
                adapter=adapter,
                model=model,
            )
        return _dispatch_consultation(
            project=project,
            board=board,
            scope=scope,
            project_root=project_root,
            model=model,
            stage_overrides=stage_overrides,
        )

    except Exception as exc:
        logging.exception("comms_project_decompose error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


def _dispatch_board_run(
    *,
    project: str,
    board: str,
    scope: str,
    rigor: str,
    project_root: str,
    adapter: str,
    model: str,
) -> tuple:
    """Dispatch a light or full single-agent board run for the project.

    Both tiers run ``planning/project-decompose`` — the only skill that emits
    ``type=feature`` cards. (The features.py mirror routes 'full' to
    ``planning/plan``, but that skill emits a task DAG for a *goal*, which would
    trip the >=2-features gate; the correct project-level emitter is
    project-decompose. 'full' differs only by a deeper instruction.)
    """
    from pathly_orchestrator.db.connection import get_db as _get_db
    from pathly_orchestrator.db.queries.comms import post_message as _post_message
    from pathly_orchestrator.supervisor.board_run import start_board_run

    skill = "planning/project-decompose"
    if rigor == "full":
        instructions = (
            f"Decompose the big spec on the '{project}' project board into 2-5 sibling "
            f"features. Do a thorough pass: read the full spec + any project-level "
            f"artifacts, wire depends_on between features, and seed a rich starting "
            f"SPEC.md per feature under pathly/features/<slug>/."
        )
    else:
        instructions = (
            f"Decompose the big spec on the '{project}' project board into 2-5 sibling "
            f"features. Post each as a type=feature card and scaffold "
            f"pathly/features/<slug>/SPEC.md."
        )

    _storage_path_str = ""
    if project_root:
        try:
            import os

            _storage_path_str = os.path.join(project_root, "pathly", "project")
            os.makedirs(_storage_path_str, exist_ok=True)
        except Exception:
            pass

    _caps = None
    try:
        from pathly_orchestrator.skills.compose import build_adapter_caps

        _caps = build_adapter_caps(adapter or "claude", kind="dag")
    except Exception:
        pass

    def _board_post(text: str, phase: str | None = None) -> None:
        try:
            c = _get_db()
            mid = _post_message(
                c,
                board=board,
                scope=scope,
                from_agent="system",
                type="status",
                text=text,
            )
            payload: dict = {
                "type": "COMMS_UPDATE",
                "event": "project_decompose",
                "project": project,
                "message_id": mid,
                "board": board,
                "scope": scope,
            }
            if phase:
                payload["phase"] = phase
            _broadcast_comms(scope, payload)
        except Exception:
            logging.debug("project_decompose lifecycle post failed", exc_info=True)

    def _on_start(_run_id: str) -> None:
        _board_post(f"decomposing project via {rigor}…", phase="running")

    def _on_done(_run_id: str, res) -> None:
        if isinstance(res, dict) and res.get("error"):
            if res.get("announced"):
                return
            err = str(res.get("error"))
            low = err.lower()
            if (
                res.get("status") == "aborted"
                or "stop" in low
                or "abort" in low
                or "kill" in low
            ):
                _board_post("project decomposition stopped", phase="stopped")
                return
            _board_post(f"project decomposition failed — {err[:300]}", phase="error")
            return
        _board_post("project decomposition finished", phase="done")

    result = start_board_run(
        board,
        scope,
        "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill=skill,
        agent="planner",
        broadcast_fn=_broadcast_runner,
        on_start=_on_start,
        on_done=_on_done,
        storage_path=_storage_path_str,
        caps=_caps,
    )

    if result.get("ok"):
        result["rigor"] = rigor
        result["project"] = project
        return jsonify(result), 200

    reason = result.get("reason") or result.get("error") or ""
    status_code = {"board_busy": 409}.get(reason, 400)
    result["rigor"] = rigor
    result["project"] = project
    return jsonify(result), status_code


def _dispatch_consultation(
    *,
    project: str,
    board: str,
    scope: str,
    project_root: str,
    model: str,
    stage_overrides: Optional[dict] = None,
) -> tuple:
    """Dispatch a project-consultation FSM flow for the project."""
    from pathly_orchestrator.db.connection import get_db as _get_db
    from pathly_orchestrator.db.queries.comms import post_message as _post_message
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.goal_executor import _safe_call
    from pathly_orchestrator.supervisor.registry import get_state

    if board_lock.holder(board, scope) is not None:
        return (
            jsonify(
                {
                    "ok": False,
                    "reason": "board_busy",
                    "error": "board is busy (a run holds the lock)",
                }
            ),
            409,
        )
    existing = get_state(scope)
    if existing is not None and existing.status in (
        "running",
        "paused",
        "awaiting_decision",
    ):
        return (
            jsonify(
                {
                    "ok": False,
                    "reason": "board_busy",
                    "error": (
                        f"a pipeline run is already active for {scope!r} "
                        f"(status={existing.status})"
                    ),
                }
            ),
            409,
        )

    # topic = the normalized project_root scope, so the PLANNING feature-count gate
    # (which reads scope = flow topic) counts features at the SAME scope the skill posts
    # them + comms_context reads them. Storage is pinned to pathly/project/ by the flow's
    # fixed storage_path (decoupled from this path-like topic).
    topic = project
    if project_root:
        try:
            import os

            os.makedirs(
                os.path.join(project_root, "pathly", "project"),
                exist_ok=True,
            )
        except Exception:
            pass

    from pathly_orchestrator.supervisor.api import start_run
    from pathly_orchestrator.supervisor.goal_executor import _reset_fsm_state_for_flow

    _reset_fsm_state_for_flow("project-consultation", topic, project_root)

    def _board_post(text: str, phase: str | None = None) -> None:
        try:
            c = _get_db()
            mid = _post_message(
                c,
                board=board,
                scope=scope,
                from_agent="system",
                type="status",
                text=text,
            )
            payload: dict = {
                "type": "COMMS_UPDATE",
                "event": "project_decompose",
                "project": project,
                "message_id": mid,
                "board": board,
                "scope": scope,
            }
            if phase:
                payload["phase"] = phase
            _broadcast_comms(scope, payload)
        except Exception:
            logging.debug("project_consultation lifecycle post failed", exc_info=True)

    def _on_done(_run_id: str, res) -> None:
        if isinstance(res, dict) and res.get("error"):
            if res.get("announced"):
                return
            err = str(res.get("error"))
            low = err.lower()
            if (
                res.get("status") == "aborted"
                or "stop" in low
                or "abort" in low
                or "kill" in low
            ):
                _board_post("project consultation stopped", phase="stopped")
                return
            _board_post(f"project consultation failed — {err[:300]}", phase="error")
            return
        _board_post("project consultation finished", phase="done")

    try:
        state = start_run(
            topic=topic,
            flow="project-consultation",
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=_broadcast_runner,
            interactive=False,
            on_done=_on_done,
            stage_overrides=stage_overrides,
        )
    except ValueError as exc:
        return (
            jsonify({"ok": False, "reason": "board_busy", "error": str(exc)}),
            409,
        )

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(_board_post, "project consultation started…", "running")
    return (
        jsonify(
            {
                "ok": True,
                "run_id": run_id,
                "rigor": "consultation",
                "project": project,
                "status": "started",
            }
        ),
        200,
    )
