"""
Event types for EVENTS.jsonl.

Each event is a JSON object appended as one line to plans/<feature>/EVENTS.jsonl.
The LLM writes these directly using its Write/Bash tools — it does not import this file.
This file is the authoritative schema reference.
CLI consumers depend on field names. Any field rename requires a schema_version
bump and a migration function here before merging.

Event order: the LLM writes a AGENT_SPAWNED event before spawning, then an
AGENT_DONE event after the agent reports back. All other events are written
immediately when the condition is detected.
"""

# ── Schema reference ──────────────────────────────────────────────────────────
#
# All events share these base fields:
#   schema_version int — event schema version, currently 1
#   type       str   — one of the TYPE constants below
#   ts         str   — ISO-8601 UTC, e.g. "2026-05-11T10:30:00Z"
#
# COMMAND — first event, written when /team-flow starts
#   feature    str   — feature name, e.g. "security-fixes"
#   rigor      str   — "lite" | "standard" | "strict"
#   entry      str   — "discovery" | "plan" | "build" | "test"
#   auto_flow  bool  — true if fast mode
#
# AGENT_SPAWNED — written before each subagent spawn
#   agent      str   — "planner" | "builder" | "reviewer" | "tester" | "architect" | "retro" | "explore"
#   model      str   — model ID, e.g. "claude-sonnet-4-6"
#   conversation int — 0 for non-build agents, 1+ for build/review/test
#   role       str   — short description, e.g. "Conv 1 code fixes"
#
# AGENT_DONE — written after agent reports back (fill in actual counts from agent output)
#   agent      str   — matches the AGENT_SPAWNED event
#   model      str   — model ID
#   conversation int — same as AGENT_SPAWNED
#   result     str   — "PASS" | "FAIL" | "DONE" | "BLOCKED"
#   tokens_in  int   — input tokens (from agent self-report or 0 if unknown)
#   tokens_out int   — output tokens
#   total_tokens int — tokens_in + tokens_out (or provider-reported total)
#   cost_usd   float — cost in USD (0.0 if unknown)
#   tool_uses  int   — number of tool calls made
#   wall_seconds int — elapsed seconds
#   ts         str   — ISO-8601 UTC timestamp
#   schema_version int — event schema version
# AGENT_DONE optional:
#   summary          str   — semantic result text written by the agent; used as authoritative result by the supervisor
#   trace_id         str   — OTel trace ID
#   span_id          str   — OTel span ID
#   cost_source      str   — "estimated" | "provider_reported" | "unpriced" (default "unpriced")
#   cache_read_tokens  int — prompt cache read tokens (default 0)
#   cache_write_tokens int — prompt cache write tokens (default 0)
#
# AGENT_DONE required: agent, model, conversation, result, tokens_in, tokens_out,
#   total_tokens, cost_usd, tool_uses, wall_seconds, ts, schema_version
# AGENT_DONE optional: summary, trace_id, span_id,
#   cost_source (default "unpriced"), cache_read_tokens (default 0), cache_write_tokens (default 0)
#
# FILE_CREATED — written when a feedback file appears in plans/<feature>/feedback/
#   file       str   — filename, e.g. "REVIEW_FAILURES.md"
#   created_by str   — agent name
#   conversation int — current conversation number
#
# FILE_DELETED — written when a feedback file is resolved and deleted
#   file       str   — filename
#   deleted_by str   — agent name
#   conversation int — current conversation number
#
# RETRY — written after routing a fix agent for a feedback file
#   retry_key  str   — "conv-N:FILE.md", e.g. "conv-2:REVIEW_FAILURES.md"
#   count      int   — retry number (1, 2, …)
#
# NO_DIFF — written when builder made no code changes after claiming to fix a failure
#   conversation int — current conversation number
#
# STATE_TRANSITION — written when FSM state changes
#   from_state str   — previous FSM state name
#   to_state   str   — new FSM state name

# ── Example EVENTS.jsonl snippet ─────────────────────────────────────────────
#
# {"type":"COMMAND","feature":"security-fixes","rigor":"lite","entry":"plan","auto_flow":false,"ts":"2026-05-11T09:00:00Z"}
# {"type":"AGENT_SPAWNED","agent":"planner","model":"claude-sonnet-4-6","conversation":0,"role":"write 4 lite plan files","ts":"2026-05-11T09:00:05Z"}
# {"type":"AGENT_DONE","agent":"planner","model":"claude-sonnet-4-6","conversation":0,"result":"DONE","tokens_in":20000,"tokens_out":5000,"cost_usd":0.0,"tool_uses":11,"wall_seconds":105,"ts":"2026-05-11T09:01:50Z"}
# {"type":"STATE_TRANSITION","from_state":"PLANNING","to_state":"PLAN_DONE","ts":"2026-05-11T09:01:50Z"}
# {"type":"AGENT_SPAWNED","agent":"builder","model":"claude-sonnet-4-6","conversation":1,"role":"Conv 1 code fixes","ts":"2026-05-11T09:05:00Z"}
# {"type":"AGENT_DONE","agent":"builder","model":"claude-sonnet-4-6","conversation":1,"result":"DONE","summary":"builder conv 1 DONE","tokens_in":22000,"tokens_out":4000,"cost_usd":0.0,"tool_uses":23,"wall_seconds":85,"ts":"2026-05-11T09:06:25Z"}
# {"type":"STATE_TRANSITION","from_state":"BUILDING_CONV_1","to_state":"REVIEWING_CONV_1","ts":"2026-05-11T09:06:25Z"}

CURRENT_SCHEMA_VERSION = 1

TYPE_COMMAND = "COMMAND"
TYPE_AGENT_SPAWNED = "AGENT_SPAWNED"
TYPE_AGENT_DONE = "AGENT_DONE"
TYPE_FILE_CREATED = "FILE_CREATED"
TYPE_FILE_DELETED = "FILE_DELETED"
TYPE_RETRY = "RETRY"
TYPE_NO_DIFF = "NO_DIFF"
TYPE_STATE_TRANSITION = "STATE_TRANSITION"
TYPE_STAGE_RECONCILIATION_FAILURE = "STAGE_RECONCILIATION_FAILURE"
# Schema: {"type": "STAGE_RECONCILIATION_FAILURE", "topic": str, "stage": str,
#           "exit_code": int, "ts": str (ISO-8601)}
# Written when a PTY billing POST does not arrive within the reconciliation
# window after an early FSM advance.

TYPE_BILLING_UPDATE = "BILLING_UPDATE"
# Schema: {"type": "BILLING_UPDATE", "agent": str, "conversation": int|null,
#           "cost_usd": float, "tokens_in": int, "tokens_out": int,
#           "total_tokens": int, "wall_seconds": int, "tool_uses": int,
#           "ts": str (ISO-8601)}
# Appended by _patch_last_agent_done to augment an AGENT_DONE with real cost/token data;
# SSE forward-tailer re-broadcasts the new row to Studio. (Append-only; no in-place mutation.)
#
# BILLING_UPDATE required: agent, conversation, cost_usd, tokens_in, tokens_out,
#   total_tokens, wall_seconds, ts
# BILLING_UPDATE optional: tool_uses,
#   cost_source (default "unpriced"), cache_read_tokens (default 0), cache_write_tokens (default 0)

TYPE_STAGE_INTERACTIVE_DONE = "STAGE_INTERACTIVE_DONE"
# Schema: {"type": "STAGE_INTERACTIVE_DONE", "topic": str, "stage": str, "ts": str}
# Written when interactive mode kills the PTY after early AGENT_DONE detection.

AGENTS = {"planner", "builder", "reviewer", "tester", "architect", "retro", "explore"}
RESULTS = {"PASS", "FAIL", "DONE", "BLOCKED"}
