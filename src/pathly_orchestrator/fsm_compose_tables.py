"""Static lookup tables for prompt composition.

Leaf module: the agent groupings, menu labels, state→command map, per-skill role map and
fix-mode artifact map that several compose modules read. Kept apart so adding a role or a
menu label never touches prompt-building code.
"""

from __future__ import annotations

_AGENT_GROUPS = {
    "architect": "planning",
    "builder": "building",
    "designer": "building",
    "explorer": "research",
    "orchestrator": "support",
    "planner": "planning",
    "po": "planning",
    "quick": "support",
    "reviewer": "quality",
    "scout": "research",
    "tester": "quality",
    "web-researcher": "research",
}

_CODEX_EXPLORER_AGENTS = {"explorer", "quick", "scout", "web-researcher"}

_MENU_LABELS = {
    "STORMING": "Refine the idea and choose the first planning step.",
    "PLANNING": "Draft or revise the implementation plan.",
    "DESIGNING": "Shape the UI or flow design before building.",
    "BUILDING": "Implement the current plan.",
    "REVIEWING": "Review the build and decide whether to loop back.",
    "TESTING": "Verify the feature and capture failures if any.",
    "RETRO": "Close out the feature and capture lessons.",
    "DONE": "Feature complete.",
}

_STATE_TO_COMMAND = {
    "STORMING": "/pathly storm",
    "PLANNING": "/pathly plan",
    "DESIGNING": "/pathly design",
    "BUILDING": "/pathly build",
    "REVIEWING": "/pathly review",
    "TESTING": "/pathly test",
    "RETRO": "/pathly retro",
    "DONE": "/pathly end",
}

_SCHEMA_VERSION = "1"

_SKILL_AGENT_ROLE: dict[str, str] = {
    "team/build": "builder",
    "team/review": "reviewer",
    "team/test": "tester",
    "team/plan": "planner",
    "team/design": "designer",
    "team/retro": "planner",
}

# Smart fix-routing (fix mode) — role -> the artifact that role corrects when routed a
# feedback file. Only these four are "root-cause" roles: they own a decision artifact
# upstream of the code, so a routed hand-off means "fix your artifact, then hand off to
# the builder" rather than "fix the code" (builder/reviewer/human are excluded — see
# build_prompt_for_agent). Mirrors DESIGN.md ss3.1 (deliberately NOT artifact-manifest.yaml's
# po -> PO_NOTES.md — ss3.1 pins po's fix-mode artifact to USER_STORIES.md, the file the team
# pipeline actually keeps requirements in; reconciling the two is a follow-up, DESIGN.md risk #5).
_FIX_MODE_ARTIFACT: dict[str, str] = {
    "po": "USER_STORIES.md",
    "planner": "IMPLEMENTATION_PLAN.md",
    "architect": "ARCHITECTURE_PROPOSAL.md",
    "designer": "DESIGN.md",
}
