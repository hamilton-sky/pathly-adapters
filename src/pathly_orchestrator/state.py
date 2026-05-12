"""
FSM state for STATE.json.

The LLM writes STATE.json directly — it does not import this file.
This file is the authoritative schema reference for STATE.json content.

STATE.json lives at plans/<feature>/STATE.json and is rewritten after every event.

── Schema ────────────────────────────────────────────────────────────────────

{
  "current": "<FSM state name>",    // see STATES below
  "feature": "<feature-name>",
  "rigor": "lite|standard|strict",
  "current_conversation": 0,        // 0 = not in build stage yet; 1+ = active conv
  "retry_count_by_key": {           // key = "conv-N:FILENAME.md"
    "conv-2:REVIEW_FAILURES.md": 1
  },
  "iteration_by_stage": {           // key = FSM stage name, value = attempt count
    "BUILDING": 2
  },
  "updated_at": "2026-05-11T10:30:00Z"
}

── FSM States ────────────────────────────────────────────────────────────────
"""

STATES = {
    "IDLE":               "Pipeline not started",
    "DISCOVERING":        "Explore/audit agent running",
    "PLANNING":           "Planner agent running",
    "PLAN_DONE":          "4 plan files written, awaiting build or escalator decision",
    "CONSULT_OPEN":       "Architect consult file open (/pathly meet)",
    "BUILDING":           "Builder agent running",
    "REVIEWING":          "Reviewer agent running",
    "REVIEW_BLOCKED":     "REVIEW_FAILURES.md present — routing to builder",
    "TESTING":            "Tester agent running",
    "TEST_BLOCKED":       "TEST_FAILURES.md present — routing to builder or user",
    "BLOCKED_ON_HUMAN":   "HUMAN_QUESTIONS.md present — pipeline paused for user",
    "RETRO":              "Retro agent running",
    "DONE":               "All conversations complete, retro written",
}

VALID_STATES: frozenset[str] = frozenset(STATES.keys())

TRANSITIONS: dict[str, frozenset[str]] = {
    "IDLE":             frozenset(["DISCOVERING", "PLANNING", "BUILDING", "BLOCKED_ON_HUMAN"]),
    "DISCOVERING":      frozenset(["PLANNING", "IDLE", "BLOCKED_ON_HUMAN"]),
    "PLANNING":         frozenset(["PLAN_DONE", "BUILDING", "BLOCKED_ON_HUMAN"]),
    "PLAN_DONE":        frozenset(["BUILDING", "CONSULT_OPEN", "BLOCKED_ON_HUMAN"]),
    "CONSULT_OPEN":     frozenset(["PLANNING", "BUILDING", "PLAN_DONE", "BLOCKED_ON_HUMAN"]),
    "BUILDING":         frozenset(["REVIEWING", "TESTING", "BLOCKED_ON_HUMAN", "DONE"]),
    "REVIEWING":        frozenset(["BUILDING", "REVIEW_BLOCKED", "BLOCKED_ON_HUMAN", "DONE"]),
    "REVIEW_BLOCKED":   frozenset(["BUILDING", "BLOCKED_ON_HUMAN"]),
    "TESTING":          frozenset(["RETRO", "TEST_BLOCKED", "BLOCKED_ON_HUMAN", "DONE"]),
    "TEST_BLOCKED":     frozenset(["BUILDING", "TESTING", "BLOCKED_ON_HUMAN"]),
    "BLOCKED_ON_HUMAN": VALID_STATES,
    "RETRO":            frozenset(["DONE", "BLOCKED_ON_HUMAN"]),
    "DONE":             frozenset(),
}

# ── Example STATE.json ────────────────────────────────────────────────────────
#
# {
#   "current": "REVIEWING",
#   "feature": "security-fixes",
#   "rigor": "lite",
#   "current_conversation": 2,
#   "retry_count_by_key": {
#     "conv-2:REVIEW_FAILURES.md": 1
#   },
#   "iteration_by_stage": {
#     "BUILDING": 2
#   },
#   "updated_at": "2026-05-11T10:45:00Z"
# }
#
# iteration_by_stage is optional. When present, each key is an FSM stage name
# and each value is the number of times that stage has been entered. This
# supplements retry_count_by_key (which tracks per-file retry counts) with a
# coarser per-stage view.
