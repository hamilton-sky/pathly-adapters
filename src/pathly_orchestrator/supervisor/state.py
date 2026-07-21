"""RunnerState dataclass and related constants."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("pathly.supervisor")

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
    # UI-configurable mode: True = visible PTY killed on AGENT_DONE; False = headless/reconciliation
    interactive: bool = True
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
    _agent_question_answer: Optional[str] = field(
        default=None, repr=False, compare=False
    )
    _agent_question_event: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )

    # OTel-compatible trace context — set at run start / per stage
    trace_id: str = ""  # 32-char hex, set once at run start
    span_id: str = ""  # 16-char hex, set per stage invocation

    # telemetry-three-tier — board/single/loop executors spawn agents WITHOUT a
    # registry RunnerState, so api_lifecycle._write_stage_telemetry never fires for
    # them. These let the executor own the projection itself (in _run_stage_via_terminal):
    #   executor_owned_telemetry — write the invocation+span here (FSM/team leave it False,
    #                              since api_lifecycle covers them — prevents double-counting)
    #   scope_tier               — board tier tag for roll-up (feature|project|global)
    #   goal_trace_id/goal_span_id — goal=trace, task=span: the goal's root span, so a
    #                              DAG run's per-task spans share one trace under it
    executor_owned_telemetry: bool = field(default=False, repr=False, compare=False)
    scope_tier: str = "feature"
    goal_trace_id: str = ""
    goal_span_id: str = ""

    # Runtime-config seam (§5, DAG scheduler) — populated by start_run; carried
    # into TaskWorkspace.env so workers inherit the shared DB path and FSM port.
    db_path: str = ""  # resolved DB file path; "" means use get_db() default
    fsm_port: int = 8765  # FSM HTTP port (mirrors PATHLY_FSM_HTTP_PORT default)

    # Set when this run is a goal decompose/executor — the terminal planner stage is
    # told to seed THIS existing goal's DAG instead of finding-or-creating its own.
    goal_id: str = ""

    # Flow-gate-preview (P2): transient, per-run, per-stage prompt overrides from the gate
    # ({state: prompt}), keyed by FSM state. In-memory ONLY — never written to public_dict()
    # / the runner_state DB mirror, so it dies with the run and never shows up as a "saved"
    # config (contrast: the PERSISTENT stage_configs.{ability_ids,excluded_sections} selection).
    stage_overrides: dict = field(default_factory=dict, repr=False, compare=False)

    # Resolved on-disk storage dir for this run. Goal-tier is board-scoped and nested:
    # pathly/features/<feature>/goals/<slug> (feature) or pathly/project/goals/<slug>
    # (project/global) — see goal_decomposer._goal_storage_dir. Never the flat pathly/goals/.
    storage_path: str = ""

    # Active terminal tab id — set while a terminal-mode stage is in flight
    active_tab_id: str = ""

    # Broadcast callback — stored so abort_run() can send SSE without a broadcast_fn arg
    _broadcast_fn: Optional[Callable] = field(default=None, repr=False, compare=False)

    # Kind string for error state
    error_kind: Optional[str] = None

    # Set True by the ■ Stop route (/comms/goals/stop) right before it aborts, so the
    # run's on_done stays quiet — the route already posted the "stopped" board message.
    # A killed runner tab leaves this False, so on_done becomes the sole announcer that
    # clears the board's "Decomposing…/Running…" timer pill.
    stop_announced: bool = field(default=False, repr=False, compare=False)

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
            "storage_path": self.storage_path,
        }
