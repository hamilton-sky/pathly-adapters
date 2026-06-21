"""Pipeline metrics collector.

Subscribes to the EventBus and aggregates per-session counters.
Resets on server restart — use the DB (AGENT_DONE events) for persistent history.

Usage:
    from pathly_orchestrator.metrics import _collector
    snap = _collector.snapshot()  # returns a plain dict
"""

from __future__ import annotations

import threading

from pathly_orchestrator.event_bus import _bus

# Backwards transitions that represent rework cycles.
_REWORK_EDGES: frozenset[tuple[str, str]] = frozenset(
    {
        ("REVIEWING", "BUILDING"),
        ("TESTING", "REVIEWING"),
        ("TESTING", "BUILDING"),
    }
)


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Cost / tokens — session-level, resets on server restart.
        self.cost_usd: float = 0.0
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        # Pipeline lifecycle counters.
        self.pipelines_started: int = 0
        self.pipelines_done: int = 0
        self.pipelines_errored: int = 0
        # State-visit histogram: state-name → count.
        self.stage_visits: dict[str, int] = {}
        # Agent-invocation histogram: agent-name → count.
        self.agent_invocations: dict[str, int] = {}
        # Rework cycles (backwards FSM transitions).
        self.feedback_loops: int = 0
        # Gate-failure count.
        self.gate_failures: int = 0

        _bus.subscribe("AGENT_DONE", self._on_agent_done)
        _bus.subscribe("STATE_TRANSITION", self._on_state_transition)
        _bus.subscribe("GATE_FAILED", self._on_gate_failed)

    def _on_agent_done(self, data: dict) -> None:
        with self._lock:
            self.cost_usd += float(data.get("cost_usd") or 0.0)
            self.tokens_in += int(data.get("tokens_in") or 0)
            self.tokens_out += int(data.get("tokens_out") or 0)
            agent = str(data.get("agent") or "unknown")
            self.agent_invocations[agent] = self.agent_invocations.get(agent, 0) + 1

    def _on_state_transition(self, data: dict) -> None:
        frm = str(data.get("from") or "")
        to = str(data.get("to") or "")
        with self._lock:
            if to:
                self.stage_visits[to] = self.stage_visits.get(to, 0) + 1
            # Initial assignment (no prior state) = new pipeline started.
            if not frm and to:
                self.pipelines_started += 1
            elif to == "DONE":
                self.pipelines_done += 1
            if (frm, to) in _REWORK_EDGES:
                self.feedback_loops += 1

    def _on_gate_failed(self, data: dict) -> None:
        with self._lock:
            self.gate_failures += 1

    def snapshot(self) -> dict:
        """Thread-safe point-in-time snapshot of all counters."""
        with self._lock:
            return {
                "cost_usd": round(self.cost_usd, 4),
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "pipelines_started": self.pipelines_started,
                "pipelines_done": self.pipelines_done,
                "pipelines_errored": self.pipelines_errored,
                "feedback_loops": self.feedback_loops,
                "gate_failures": self.gate_failures,
                "stage_visits": dict(self.stage_visits),
                "agent_invocations": dict(self.agent_invocations),
            }


_collector = MetricsCollector()
