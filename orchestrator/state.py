"""
FSM state for STATE.json.

The LLM writes STATE.json directly — it does not import this file.
This file is the authoritative schema reference for STATE.json content.

STATE.json lives at plans/<feature>/STATE.json and is rewritten after every event.

── Schema ────────────────────────────────────────────────────────────────────

{
  "name": "<FSM state name>",      // see STATES below
  "feature": "<feature-name>",
  "rigor": "lite|standard|strict",
  "current_conversation": 0,        // 0 = not in build stage yet; 1+ = active conv
  "retry_count_by_key": {           // key = "conv-N:FILENAME.md"
    "conv-2:REVIEW_FAILURES.md": 1
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

# ── Example STATE.json ────────────────────────────────────────────────────────
#
# {
#   "name": "REVIEWING",
#   "feature": "security-fixes",
#   "rigor": "lite",
#   "current_conversation": 2,
#   "retry_count_by_key": {
#     "conv-2:REVIEW_FAILURES.md": 1
#   },
#   "updated_at": "2026-05-11T10:45:00Z"
# }
