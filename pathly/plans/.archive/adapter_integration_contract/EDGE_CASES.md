---
name: Edge Cases
---
# Adapter Integration Contract — Edge Cases

| Scenario | Expected behavior |
|---|---|
| Feedback file exists and target agent is a Pathly agent (builder, reviewer, etc.). | `decision = "block"`; adapter routes to the named agent automatically. |
| Feedback file exists and target is `"human"`. | `decision = "escalate"`; adapter surfaces the file to the user and halts. |
| Feedback file exists but is not recognized (unknown routing). | `decision = "escalate"`; adapter halts and reports the warning. |
| State recovery finds corrupt or contradictory `STATE.json`. | `decision = "escalate"`; adapter stops rather than improvising. |
| `complete_stage` discovers a gate failure after work is done. | Adapter reports the failure; does not assume completion; FSM surfaces feedback or escalates. |
| Retry limit exceeded for a feedback round. | `decision = "escalate"`; adapter writes `HUMAN_QUESTIONS.md` and halts cleanly. |
| Schema version is newer but still additive. | Adapter warns and proceeds if the contract shape remains compatible. |
| `warnings` includes stale or aged-out context. | Adapter shows the warning without reinterpreting it as a state transition. |
| Multiple feedback files exist simultaneously. | FSM resolves one file at a time via `route_feedback`; adapter does not improvise precedence. |
| `agent_hint` keys are the new neutral names but consumer expects `codex_role`. | Consumer reads `codex_subagent` compat field (frozen with old keys) until it migrates to `agent_hint`. |
| `complete_stage` returns `current_state` instead of `next_state`. | Adapter reads `current_state` on all responses — no endpoint-specific key branching needed. |
