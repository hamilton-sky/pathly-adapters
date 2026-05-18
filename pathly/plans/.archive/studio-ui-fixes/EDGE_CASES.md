# studio-ui-fixes — Edge Cases

## Event log edge cases

| Case | Expected behaviour |
|---|---|
| FSM_START has no `ts` | Shows `—` in timestamp column, not "Invalid" |
| Event has neither `from/to` nor `reason` nor `detail` | Detail column is empty string — no crash |
| EVENTS.jsonl is empty | "No events yet" placeholder shown |
| EVENTS.jsonl has a malformed JSON line | Line is silently skipped; rest renders normally |
| Event has `from` but not `to` (or vice versa) | Does not show `→`; falls through to reason/detail fallback |

## Pipeline states edge cases

| Case | Expected behaviour |
|---|---|
| `fsmState` is null (no STATE.json) | Pipeline shows fallback states dimmed — Idle |
| `fsmState.flow` is empty string | Flow YAML read fails silently; fallback states used |
| Flow YAML exists but has no `states:` block | Regex match fails; fallback states used |
| Active state is not in the pipeline list | State highlighted nowhere; no crash (activeIdx = -1) |
| `pipelineStates` updates while viewing | Component re-renders with new list |

## PROGRESS.md parser edge cases

| Case | Expected behaviour |
|---|---|
| No `## Conversation Breakdown` heading | Returns empty array; sidebar PLAN shows "No conversations" |
| Conversation Breakdown table has no rows (only header) | Returns empty array |
| Status column text is lowercase | `.toUpperCase()` normalises it |
| PROGRESS.md file does not exist | `readFile` rejects; `catch` sets `planConvs = []` |

## Debugs / Explorations sidebar edge cases

| Case | Expected behaviour |
|---|---|
| `pathly/debugs/` does not exist | `listDirs` rejects; section shows empty gracefully (catch already present) |
| A debug subfolder is empty (no files) | Subfolder row renders with no children — no crash |
| A debug file is not `.md` | Still shows and opens in editor (editor shows raw text) |
| Filter text typed in sidebar | Filters debug/explore items same as template items |
