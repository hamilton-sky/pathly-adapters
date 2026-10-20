"""The valid requests of the GET routes of the chief gate audit (chief-agent 08, round 7): the
queries that get past each view's own validation, so a hostile value in one key of one of them
reaches the sink and not just the 400. Split out of ``chief_audit_world`` (the 400-line ratchet).
"""

from __future__ import annotations

from chief_audit_world import DEMO, Variant

GET_VARIANTS = {
    "/comms/artifacts/<artifact_id>/section": lambda w: [
        Variant(
            "by id",
            {"scope": DEMO, "anchor": "scope", "trail": "t"},
            {"artifact_id": w.artifact_id()},
        ),
        Variant(
            "another project's",
            {"scope": DEMO},
            {"artifact_id": w.foreign_id},
        ),
    ],
    "/comms/artifacts/section": lambda w: [
        Variant(
            "by path",
            {
                "artifact": f"pathly/features/{DEMO}/PLAN.md",
                "scope": DEMO,
                "anchor": "scope",
                "trail": "t",
            },
        )
    ],
    "/status": lambda w: [Variant("status", {"topic": DEMO})],
    "/runner/status": lambda w: [Variant("status", {"topic": DEMO})],
    "/comms": lambda w: [Variant("board", {"feature": DEMO})],
    "/comms/tasks": lambda w: [Variant("tasks", {"feature": DEMO, "goal_id": w.goal})],
    "/comms/goals": lambda w: [Variant("goals", {"feature": DEMO})],
    "/comms/artifacts": lambda w: [
        Variant("artifacts", {"scope": DEMO, "message_id": w.artifact})
    ],
    "/comms/goals/refs-coverage": lambda w: [Variant("coverage", {"goal_id": w.goal})],
    "/comms/run/status": lambda w: [Variant("status", {"scope": DEMO})],
    "/hq/context": lambda w: [Variant("packet", {"board": DEMO})],
    "/flows/stage-config": lambda w: [
        Variant("stage", {"feature": DEMO, "stage": "BUILDING"})
    ],
}
