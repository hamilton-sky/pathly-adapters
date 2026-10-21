"""The valid requests of the POST routes of the chief gate audit (chief-agent 08, round 7): the
bodies that get past each view's own validation, one or more per route, so a hostile value in one
key of one of them reaches the sink and not just the 400. Split out of ``chief_audit_world`` (the
400-line ratchet). A baseline that stops early hides its route: ``test_chief_gate_audit.py``
asserts that each baseline named in ``REACHES`` gets to the work the route exists for.
"""

from __future__ import annotations

from chief_audit_world import DEMO, Variant


def _post_variants(world) -> list[Variant]:
    base = {"from": "chief", "feature": DEMO, "text": "hello"}
    return [
        Variant("status", {**base, "type": "status"}),
        Variant(
            "goal",
            {**base, "type": "goal", "slug": lambda: world.fresh_name("ship")},
        ),
        Variant(
            "task",
            {
                **base,
                "type": "task",
                "goal_id": world.goal,
                "files": ["src/x.py"],
                "lane": "a",
                "executor": "single",
                "no_refs": "none yet",
            },
        ),
        Variant(
            "artifact",
            {
                **base,
                "type": "artifact",
                "artifact_path": str(world.plan),
                "artifact_type": "PLAN",
                "summary": "the plan",
            },
        ),
        Variant(
            "decision",
            {**base, "type": "decision", "supersedes": [world.decision_a]},
        ),
        Variant(
            "question",
            {**base, "type": "question", "options": [{"id": "a", "label": "A"}]},
        ),
    ]


def _goal_run(world) -> list[Variant]:
    return [
        Variant(executor, {"goal_id": world.goal, "executor": executor})
        for executor in ("team", "loop", "single")
    ]


def _runs(world) -> list[Variant]:
    return [
        Variant("flow", {"kind": "flow", "flow": "team", "scope": DEMO}),
        Variant("single", {"kind": "single", "scope": DEMO, "board": "feature"}),
        Variant("goal", {"kind": "goal", "goal_id": world.goal, "scope": DEMO}),
    ]


def _run_verbs(world) -> list[Variant]:
    retry = {
        "flow": "team",
        "max_iterations": 3,
        "max_cost_usd": 1,
        "model": "m",
        "adapter": "claude",
        "stage": "BUILDING",
    }
    return [
        Variant(
            verb,
            retry,
            {"run_id": "run-audit", "action": verb},
            lambda status=(
                "done" if verb == "retry" else "running"
            ): world.register_run(status),
        )
        for verb in ("pause", "resume", "advance", "reroute", "retry", "abort")
    ]


def _comms_run(world) -> list[Variant]:
    return [
        Variant(
            "evaluator",
            {"board": "global", "scope": "audit-board", "mode": "evaluator"},
        ),
        Variant(
            "skill",
            {
                "board": "feature",
                "scope": DEMO,
                "mode": "single-agent",
                "skill": "planning/evaluate",
            },
        ),
    ]


POST_VARIANTS = {
    "/comms/search": lambda w: [
        Variant("search", {"query": "export", "feature": DEMO})
    ],
    "/code/query": lambda w: [
        Variant(
            "query",
            {"op": "symbol", "target": "src/x.py", "scope": "(audit)"},
            prepare=w.forget_code_answers,
        )
    ],
    "/comms/post": _post_variants,
    "/comms/goals/decompose": lambda w: [
        Variant("planner", {"goal_id": w.empty_goal, "mode": "planner"}),
        Variant("consultation", {"goal_id": w.empty_goal, "mode": "consultation"}),
    ],
    "/comms/features/decompose": lambda w: [
        Variant("light", {"feature": "audit-feature", "rigor": "light"})
    ],
    "/comms/project/decompose": lambda w: [Variant("light", {"rigor": "light"})],
    "/comms/acknowledge": lambda w: [
        Variant("ack", {"message_id": w.note, "agent": "chief"}),
        Variant(
            "ack a human escalation",
            {
                "message_id": w.human_escalation,
                "agent": "chief",
                "cite": w.fresh_cite,
            },
        ),
    ],
    "/comms/supersede": lambda w: [
        Variant(
            "supersede",
            {"old_id": w.fresh_project_decision, "new_id": w.project_decision},
        )
    ],
    # A standing order for every role: it is a decision on the chief's own project board.
    "/comms/directives": lambda w: [
        Variant("directive", {"to_agent": "*", "text": "No new dependencies."})
    ],
    "/runs": _runs,
    "/comms/goals/run": _goal_run,
    "/comms/run": _comms_run,
    "/comms/tasks/run": lambda w: [Variant("task", {"message_id": w.fresh_task})],
    "/runs/<run_id>/<action>": _run_verbs,
    "/runs/<run_id>/stop": lambda w: [
        Variant("stop", {}, {"run_id": "run-audit"}, lambda: w.register_run("running")),
        Variant("stop a board run", {}, {"run_id": "run-audit"}, w.hold_board),
    ],
    "/comms/goals/stop": lambda w: [
        Variant("stop", {"goal_id": w.goal}, prepare=w.hold_board)
    ],
    "/comms/run/stop": lambda w: [Variant("stop", {"scope": DEMO}, holds="scope")],
    "/comms/tasks/stop": lambda w: [
        Variant("stop", {"message_id": w.task}, prepare=w.hold_board)
    ],
    # A chief answers by citing a message the person typed, never with words of its own.
    "/runner/agent-answer": lambda w: [
        Variant(
            "answer",
            {"topic": "audit-asking", "cite": w.fresh_cite},
            prepare=w.register_asking_run,
        )
    ],
    "/comms/answer": lambda w: [
        Variant("answer", {"question_id": w.question, "cite": w.fresh_cite})
    ],
}
