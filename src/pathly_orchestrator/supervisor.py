"""Autonomous supervisor: RunnerState registry + threaded run loop.

The supervisor sits above the FSM — it calls next_action/complete_stage but is
never imported by the FSM layer.  HTTP control endpoints (Conv 3) wire into the
registry; SSE broadcast is injected via the optional broadcast_fn callback.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("pathly.supervisor")

# ── RunnerState ────────────────────────────────────────────────────────────────

VALID_STATUSES = frozenset(
    {"idle", "running", "paused", "awaiting_decision", "aborted", "done", "error"}
)

MAX_FEEDBACK_ROUNDS = 3


@dataclass
class OpenSession:
    adapter: str
    session_id: Optional[str]
    resumable: bool


@dataclass
class RunnerState:
    topic: str
    flow: str
    project_root: str
    model: str
    timeout: int

    run_id: str = ""
    status: str = "idle"
    current_state: str = ""
    current_adapter: str = ""
    iterations: int = 0
    max_iterations: int = 10
    cost_usd_so_far: float = 0.0
    max_cost_usd: float = 1.0
    autonomy: dict = field(default_factory=dict)
    pending_menu: Optional[dict] = None

    # Internal control flags — written under the registry lock
    _pause_flag: bool = field(default=False, repr=False, compare=False)
    _abort_flag: bool = field(default=False, repr=False, compare=False)
    _decision: Optional[str] = field(default=None, repr=False, compare=False)
    _decision_event: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )

    # Session continuity
    open_session: Optional[OpenSession] = field(default=None, repr=False, compare=False)

    # Current subprocess handle — set only while a subprocess is active
    _proc: Optional[Any] = field(default=None, repr=False, compare=False)

    # Reroute override — set by /runner/reroute for the *next* stage only
    _reroute_adapter: Optional[str] = field(default=None, repr=False, compare=False)

    # Agent question — set while waiting for user to answer a denied AskUserQuestion
    _awaiting_agent_answer: bool = field(default=False, repr=False, compare=False)
    _agent_question_answer: Optional[str] = field(default=None, repr=False, compare=False)
    _agent_question_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    # Active terminal tab id — set while a terminal-mode stage is in flight
    active_tab_id: str = ""

    # Broadcast callback — stored so abort_run() can send SSE without a broadcast_fn arg
    _broadcast_fn: Optional[Callable] = field(default=None, repr=False, compare=False)

    # Kind string for error state
    error_kind: Optional[str] = None

    def public_dict(self) -> dict:
        """Return serialisable state for RUNNER_STATE.json and status API."""
        return {
            "topic": self.topic,
            "flow": self.flow,
            "project_root": self.project_root,
            "model": self.model,
            "timeout": self.timeout,
            "run_id": self.run_id,
            "status": self.status,
            "current_state": self.current_state,
            "current_adapter": self.current_adapter,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "cost_usd_so_far": self.cost_usd_so_far,
            "max_cost_usd": self.max_cost_usd,
            "autonomy": self.autonomy,
            "pending_menu": self.pending_menu,
            "error_kind": self.error_kind,
            "open_session": (
                {
                    "adapter": self.open_session.adapter,
                    "session_id": self.open_session.session_id,
                    "resumable": self.open_session.resumable,
                }
                if self.open_session
                else None
            ),
        }


# ── Registry ───────────────────────────────────────────────────────────────────

_registry: dict[str, RunnerState] = {}
_lock = threading.Lock()
_terminal_started_events: dict[str, threading.Event] = {}
_terminal_result_events: dict[str, threading.Event] = {}
_terminal_result_data: dict[str, dict] = {}


def _mirror_path(state: RunnerState) -> Path:
    return Path(state.project_root) / "pathly" / "plans" / state.topic / "RUNNER_STATE.json"


def _write_mirror(state: RunnerState) -> None:
    try:
        path = _mirror_path(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.public_dict(), indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to write RUNNER_STATE.json for %s: %s", state.topic, exc)


def recover_stale_mirrors(project_root: str) -> None:
    """On server startup, rewrite any RUNNER_STATE.json left as 'running' → 'error'.

    Scans pathly/plans/*/RUNNER_STATE.json relative to project_root.
    """
    plans_dir = Path(project_root) / "pathly" / "plans"
    if not plans_dir.is_dir():
        return
    for mirror in plans_dir.glob("*/RUNNER_STATE.json"):
        try:
            data = json.loads(mirror.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") == "running":
            data["status"] = "error"
            data["error_kind"] = "stale_restart"
            mirror.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info("Rewrote stale mirror for topic %s → error", data.get("topic"))


def get_state(topic: str) -> Optional[RunnerState]:
    with _lock:
        return _registry.get(topic)


def _set_status(state: RunnerState, status: str, broadcast_fn: Optional[Callable]) -> None:
    state.status = status
    _write_mirror(state)
    if broadcast_fn:
        try:
            broadcast_fn(
                state.topic,
                {"type": "RUNNER_STATUS", "topic": state.topic, "status": status},
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)


def _run_stage_via_terminal(
    state: RunnerState,
    instructions: str,
    adapter: str,
    model: str,
    run_id: str,
    broadcast_fn: Optional[Callable],
    session: Optional[str] = None,
    autonomy: bool = True,
) -> dict:
    from pathly_orchestrator.runner import resolve_argv

    argv = resolve_argv(adapter, instructions, model, session=session, autonomy=autonomy)
    tab_id = f"runner-{run_id[-10:]}"
    label = f"{adapter} — {state.current_state or state.status}"
    with _lock:
        state.active_tab_id = tab_id
    try:
        payload = {
            "type": "TERMINAL_SPAWN",
            "topic": state.topic,
            "run_id": run_id,
            "tab_id": tab_id,
            "label": label,
            "adapter": adapter,
            "argv": argv,
            "cwd": state.project_root,
            "prompt": instructions,
            "stage": state.current_state,
        }
        if broadcast_fn:
            broadcast_fn(state.topic, payload)
        with _lock:
            started = _terminal_started_events.setdefault(run_id, threading.Event())
            result_evt = _terminal_result_events.setdefault(run_id, threading.Event())
        if not started.wait(timeout=30):
            with _lock:
                _terminal_started_events.pop(run_id, None)
                _terminal_result_events.pop(run_id, None)
            raise RuntimeError(
                f"terminal_spawn_timeout: Studio did not spawn PTY for {tab_id} within 30s"
            )
        # Wait up to 30 min for the PTY to report its result.
        # Without a timeout, a crashed or unresponsive terminal hangs the supervisor forever.
        # (The PTY exit handler in terminal.ts POSTs /runner/terminal/result; if that POST
        # never arrives — e.g. the process exited before the exit handler fired, or the POST
        # failed — result_evt is never set and the thread blocks indefinitely.)
        _TERMINAL_RESULT_TIMEOUT = 1800
        if not result_evt.wait(timeout=_TERMINAL_RESULT_TIMEOUT):
            with _lock:
                _terminal_started_events.pop(run_id, None)
                _terminal_result_events.pop(run_id, None)
            raise RuntimeError(
                f"terminal_result_timeout: PTY for {tab_id} did not report a result within "
                f"{_TERMINAL_RESULT_TIMEOUT}s — the process likely crashed without sending an exit callback"
            )
        with _lock:
            data = _terminal_result_data.pop(run_id, {})
            _terminal_started_events.pop(run_id, None)
            _terminal_result_events.pop(run_id, None)
        return data.get("result", {})
    finally:
        with _lock:
            state.active_tab_id = ""


# ── Loop thread ────────────────────────────────────────────────────────────────

def _await_agent_question(
    state: RunnerState,
    topic: str,
    ask_q: dict,
    broadcast_fn: Optional[Callable],
) -> Optional[str]:
    """Surface a denied AskUserQuestion to the user via SSE and wait for their answer.
    Returns the answer string, or None if the run was aborted.
    """
    tool_input = ask_q.get("tool_input") or {}
    questions = tool_input.get("questions") or []
    if not questions:
        return None
    first_q = questions[0]
    question_text = first_q.get("question", "")
    options = first_q.get("options") or []

    with _lock:
        state._awaiting_agent_answer = True
        state._agent_question_answer = None
        state._agent_question_event.clear()

    if broadcast_fn:
        try:
            broadcast_fn(topic, {
                "type": "AGENT_QUESTION",
                "topic": topic,
                "question": question_text,
                "options": options,
            })
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)

    # Wait for user answer or abort
    while True:
        with _lock:
            if state._abort_flag:
                state._awaiting_agent_answer = False
                return None
            answer = state._agent_question_answer
        if answer is not None:
            break
        time.sleep(0.05)

    with _lock:
        state._awaiting_agent_answer = False
        state._agent_question_answer = None

    return answer


def _loop(state: RunnerState, broadcast_fn: Optional[Callable]) -> None:
    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator.adapters import resolve_command

    flow = state.flow
    topic = state.topic
    project_root = state.project_root
    model = state.model

    def _broadcast(payload: dict) -> None:
        if broadcast_fn:
            try:
                broadcast_fn(topic, payload)
            except Exception as exc:
                logger.warning("broadcast_fn error: %s", exc)

    try:
        while True:
            # ── Boundary: check abort ──────────────────────────────────────────
            with _lock:
                if state._abort_flag:
                    _set_status(state, "aborted", broadcast_fn)
                    return

            # ── Boundary: check pause ─────────────────────────────────────────
            with _lock:
                if state._pause_flag:
                    _set_status(state, "paused", broadcast_fn)

            while True:
                with _lock:
                    is_paused = state._pause_flag
                    abort_now = state._abort_flag
                if abort_now:
                    with _lock:
                        _set_status(state, "aborted", broadcast_fn)
                    return
                if not is_paused:
                    break
                time.sleep(0.1)

            with _lock:
                _set_status(state, "running", broadcast_fn)

            # ── Boundary: check caps ──────────────────────────────────────────
            with _lock:
                over_iter = state.iterations >= state.max_iterations
                over_cost = state.cost_usd_so_far >= state.max_cost_usd
            if over_iter or over_cost:
                with _lock:
                    state.error_kind = "cap_exceeded"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": "Cap exceeded",
                        "kind": "cap_exceeded",
                    }
                )
                return

            # ── Call FSM next_action ──────────────────────────────────────────
            try:
                response = fhc.next_action(
                    {"flow": flow, "topic": topic, "project_root": project_root}
                )
            except RuntimeError as exc:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return

            if response.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if response.get("blocked"):
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"FSM blocked: {response.get('file', '')}",
                        "kind": "subprocess",
                    }
                )
                return

            current_fsm_state = response.get("current_state", "")
            instructions = response.get("instructions", "")
            preferred_adapter = response.get("preferred_adapter", "") or "claude"

            # Apply reroute override if set
            with _lock:
                if state._reroute_adapter:
                    preferred_adapter = state._reroute_adapter
                    state._reroute_adapter = None

            # ── Session continuity ────────────────────────────────────────────
            with _lock:
                open_sess = state.open_session
                autonomy_for_adapter = state.autonomy.get(preferred_adapter, True)

            session_id: Optional[str] = None
            degraded = False

            try:
                cmd_info = resolve_command(preferred_adapter, "", "", autonomy=False)
                adapter_supports_resume = cmd_info["supports_resume"]
            except ValueError:
                adapter_supports_resume = False

            if (
                open_sess is not None
                and open_sess.adapter == preferred_adapter
                and adapter_supports_resume
                and open_sess.session_id
            ):
                session_id = open_sess.session_id
                session_action = "continued"
            else:
                session_id = None
                session_action = "opened"
                if not adapter_supports_resume:
                    degraded = True

            _broadcast(
                {
                    "type": "SESSION",
                    "topic": topic,
                    "adapter": preferred_adapter,
                    "kind": session_action,
                    "degraded": degraded,
                }
            )

            with _lock:
                state.current_state = current_fsm_state
                state.current_adapter = preferred_adapter
                _write_mirror(state)

            _broadcast(
                {
                    "type": "STAGE_CHANGE",
                    "topic": topic,
                    "state": current_fsm_state,
                    "adapter": preferred_adapter,
                    "iteration": state.iterations,
                }
            )

            # ── Invoke agent ──────────────────────────────────────────────────
            run_id = f"{topic}-{state.iterations + 1}-{int(time.time() * 1000)}"
            try:
                invoke_result = _run_stage_via_terminal(
                    state,
                    instructions,
                    preferred_adapter,
                    model,
                    run_id,
                    broadcast_fn,
                    session=session_id,
                    autonomy=autonomy_for_adapter,
                )
            except RuntimeError as exc:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return

            # ── Handle agent questions (AskUserQuestion denied in headless mode) ──────
            _MAX_QUESTION_ROUNDS = 3
            for _q_round in range(_MAX_QUESTION_ROUNDS):
                ask_q = (invoke_result or {}).get("ask_user_question")
                if not ask_q:
                    break

                tool_input = ask_q.get("tool_input") or {}
                qs = tool_input.get("questions") or []
                q_text = qs[0].get("question", "") if qs else ""

                answer = _await_agent_question(state, topic, ask_q, broadcast_fn)
                if answer is None:
                    # Aborted while waiting for answer
                    with _lock:
                        _set_status(state, "aborted", broadcast_fn)
                    return

                with _lock:
                    _set_status(state, "running", broadcast_fn)

                # Build retry instructions: prepend the user's answer so the agent
                # continues the stage task with the information it needed
                answer_block = (
                    f"CONTEXT — The user answered your question before you continue:\n"
                    f"Q: {q_text}\n"
                    f"A: {answer}\n\n"
                    f"Now proceed with the original task using this answer.\n\n"
                )
                retry_run_id = f"{run_id}-q{_q_round + 1}"
                retry_session = (invoke_result or {}).get("session_id") or session_id
                try:
                    invoke_result = _run_stage_via_terminal(
                        state,
                        answer_block + instructions,
                        preferred_adapter,
                        model,
                        retry_run_id,
                        broadcast_fn,
                        session=retry_session,
                        autonomy=autonomy_for_adapter,
                    )
                except RuntimeError as exc:
                    with _lock:
                        state.error_kind = "subprocess"
                        _set_status(state, "error", broadcast_fn)
                    _broadcast({
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    })
                    return
            # (end agent-question retry loop)

            # ── Update cost + session from invoke result ───────────────────────
            new_cost = (invoke_result or {}).get("cost_usd", 0.0) or 0.0
            new_session_id = (invoke_result or {}).get("session_id")

            with _lock:
                state.iterations += 1
                state.cost_usd_so_far += new_cost
                state.open_session = OpenSession(
                    adapter=preferred_adapter,
                    session_id=new_session_id or session_id,
                    resumable=adapter_supports_resume,
                )
                _write_mirror(state)

            _broadcast(
                {
                    "type": "COST_UPDATE",
                    "topic": topic,
                    "cost_usd": state.cost_usd_so_far,
                    "iterations": state.iterations,
                    "max_cost_usd": state.max_cost_usd,
                }
            )

            # ── Resolve stage (feedback loop + decide) ────────────────────────
            result = _resolve_stage_supervised(
                state, flow, topic, project_root, model,
                broadcast_fn, fhc
            )

            if result is None:
                # Loop was aborted or errored during resolve
                return

            if result.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if result.get("blocked"):
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Blocked: {result.get('file', '')}",
                        "kind": "subprocess",
                    }
                )
                return

            # next_state — continue loop
            if result.get("next_state"):
                continue

            # Unexpected
            with _lock:
                state.error_kind = "subprocess"
                _set_status(state, "error", broadcast_fn)
            return

    except Exception as exc:
        logger.exception("Supervisor loop crashed for topic %s", topic)
        with _lock:
            state.error_kind = "subprocess"
            try:
                _set_status(state, "error", broadcast_fn)
            except Exception:
                pass


def _resolve_stage_supervised(
    state: RunnerState,
    flow: str,
    topic: str,
    project_root: str,
    model: str,
    broadcast_fn: Optional[Callable],
    fhc,
) -> Optional[dict]:
    """Run the complete_stage feedback loop without blocking input().

    Returns a result dict (done/next_state/blocked), or None if the loop
    was aborted or errored during this phase.
    """
    resolved: list[str] = []
    feedback_rounds = 0

    def _broadcast(payload: dict) -> None:
        if broadcast_fn:
            try:
                broadcast_fn(topic, payload)
            except Exception as exc:
                logger.warning("broadcast_fn error: %s", exc)

    while True:
        # Abort check before each FSM call
        with _lock:
            if state._abort_flag:
                _set_status(state, "aborted", broadcast_fn)
                return None

        try:
            result = fhc.complete_stage(
                {
                    "flow": flow,
                    "topic": topic,
                    "project_root": project_root,
                    "resolved_files": resolved or None,
                }
            )
        except RuntimeError as exc:
            with _lock:
                state.error_kind = "subprocess"
                _set_status(state, "error", broadcast_fn)
            _broadcast(
                {
                    "type": "RUNNER_ERROR",
                    "topic": topic,
                    "message": str(exc),
                    "kind": "subprocess",
                }
            )
            return None

        resolved = []

        if result.get("done") or result.get("next_state"):
            return result

        # ── Decision point ────────────────────────────────────────────────────
        if result.get("decide"):
            menu = {
                "question": result.get("question", ""),
                "options": result.get("options", {}),
                "default": result.get("default", ""),
            }
            with _lock:
                state.pending_menu = menu
                _set_status(state, "awaiting_decision", broadcast_fn)
                state._decision = None
                state._decision_event.clear()

            _broadcast({"type": "DECISION_MENU", "topic": topic, "menu": menu})

            # Wait for a decision to be supplied
            while True:
                with _lock:
                    if state._abort_flag:
                        _set_status(state, "aborted", broadcast_fn)
                        return None
                    decision = state._decision
                if decision is not None:
                    break
                time.sleep(0.05)

            with _lock:
                state.pending_menu = None
                state._decision = None
                _set_status(state, "running", broadcast_fn)

            # Feed decision to FSM
            try:
                decision_result = fhc.complete_stage(
                    {
                        "flow": flow,
                        "topic": topic,
                        "project_root": project_root,
                        "decision": decision,
                    }
                )
            except RuntimeError as exc:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return None

            return decision_result

        # ── Blocked / feedback ────────────────────────────────────────────────
        if result.get("blocked"):
            target = result.get("target_agent", "")
            file_ = result.get("file", "")

            if target == "human":
                # Escalate — surface as error (cannot block waiting for human in headless mode)
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Human checkpoint required: {file_}",
                        "kind": "subprocess",
                    }
                )
                return None

            feedback_rounds += 1
            if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file_}",
                        "kind": "subprocess",
                    }
                )
                return None

            fb_instructions = result.get(
                "instructions", f"Resolve feedback in feedback/{file_}"
            )

            with _lock:
                if state._abort_flag:
                    _set_status(state, "aborted", broadcast_fn)
                    return None
                autonomy_for_adapter = state.autonomy.get(state.current_adapter, True)

            fb_run_id = f"{topic}-fb{feedback_rounds}-{int(time.time() * 1000)}"
            try:
                _run_stage_via_terminal(
                    state,
                    fb_instructions,
                    state.current_adapter or "claude",
                    model,
                    fb_run_id,
                    broadcast_fn,
                    session=None,
                    autonomy=autonomy_for_adapter,
                )
            except RuntimeError as exc:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return None

            resolved = [file_]
            continue

        return result


# ── Public API ────────────────────────────────────────────────────────────────

def start_run(
    topic: str,
    flow: str,
    project_root: str,
    model: str = "claude-sonnet-4-6",
    timeout: int = 600,
    max_iterations: int = 10,
    max_cost_usd: float = 1.0,
    autonomy: Optional[dict] = None,
    broadcast_fn: Optional[Callable] = None,
) -> RunnerState:
    """Start a new supervised run for *topic*.  Raises ValueError if already active."""
    import uuid as _uuid
    with _lock:
        existing = _registry.get(topic)
        if existing and existing.status in {"running", "paused", "awaiting_decision"}:
            raise ValueError(f"Run for topic {topic!r} is already active (status={existing.status})")

        state = RunnerState(
            topic=topic,
            flow=flow,
            project_root=project_root,
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=max_cost_usd,
            autonomy=autonomy or {},
            run_id=str(_uuid.uuid4()),
            _broadcast_fn=broadcast_fn,
        )
        _registry[topic] = state
        state.status = "running"
        _write_mirror(state)

    if broadcast_fn:
        try:
            broadcast_fn(
                topic,
                {
                    "type": "RUN_STARTED",
                    "topic": topic,
                    "run_id": state.run_id,
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)

    t = threading.Thread(
        target=_loop,
        args=(state, broadcast_fn),
        daemon=True,
        name=f"supervisor-{topic}",
    )
    t.start()
    return state


def pause_run(topic: str) -> None:
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._pause_flag = True


def resume_run(topic: str) -> None:
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._pause_flag = False


def abort_run(topic: str) -> None:
    """Hard-kill the in-flight subprocess (if any) and set status=aborted."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._abort_flag = True
        proc = state._proc
        active_tab_id = state.active_tab_id
        run_id = state.run_id
        broadcast_fn = state._broadcast_fn

    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass

    if active_tab_id and broadcast_fn:
        try:
            broadcast_fn(
                topic,
                {
                    "type": "TERMINAL_SIGNAL",
                    "topic": topic,
                    "signal": "term",
                    "tab_id": active_tab_id,
                    "run_id": run_id,
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)


def supply_decision(topic: str, decision: str) -> None:
    """Supply a decision for an awaiting_decision run."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        if state.status != "awaiting_decision":
            raise ValueError(f"Topic {topic!r} is not awaiting a decision (status={state.status})")
        state._decision = decision
        state._decision_event.set()


def supply_agent_answer(topic: str, answer: str) -> None:
    """Supply a user answer for a stage that asked a question (denied AskUserQuestion)."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        if not state._awaiting_agent_answer:
            raise ValueError(f"Topic {topic!r} is not awaiting an agent answer")
        state._agent_question_answer = answer
        state._agent_question_event.set()


def reroute_run(topic: str, adapter: str) -> None:
    """Override the adapter for the next stage only."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._reroute_adapter = adapter
