---
name: Edge Cases
---
# Adapter Integration Contract — Edge Cases

| Scenario | Expected behavior |
|---|---|
| Feedback file exists and is recognized. | `decision = block`; adapter surfaces the file and waits. |
| Feedback file exists but is not recognized. | `decision = escalate`; adapter halts and reports the warning. |
| State recovery finds a corrupt or contradictory FSM snapshot. | `decision = escalate`; adapter stops rather than improvising. |
| `complete_stage` discovers a gate failure after work is done. | Adapter reports the failure and does not assume completion. |
| Schema version is newer but still additive. | Adapter warns and proceeds if the contract remains compatible. |
| `warnings` includes stale context. | Adapter shows the warning without reinterpreting it as a state transition. |
