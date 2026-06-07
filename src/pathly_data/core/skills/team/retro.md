# team/retro

Stage 5 — Retrospective. Invoked by the `team` orchestrator when FSM state is RETRO.

Parse `$ARGUMENTS`: `FEATURE`.

## FSM operations

- **Transition state to X:** Write `pathly/plans/<feature>/STATE.json` `{"current": "X"}`.
  Log via: `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'STATE_TRANSITION','to':'X','ts':'<iso-timestamp>'})"`.

Every logged event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.

## Subagents

| Action | Spawn |
|---|---|
| Run retrospective | `quick` |

---

**Spawn** `quick`:
```
Route to retro [feature].
Ask the 3 retrospective questions and return the RETRO.md-ready summary.
Do not write files; quick is read-only. The retro skill/orchestrator writes RETRO.md.
```

After quick completes:
- Write `pathly/plans/[feature]/RETRO.md` with the summary provided.
- Append any extracted lessons to `LESSONS_CANDIDATE.md` (project root or pathly/plans/).

Parse the `<usage>` block from quick's response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Then invoke the `log-agent-done` skill with:
```json
{"agent":"quick","feature":"<FEATURE>","conversation":0,"result":"DONE","total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>}
```

**Generate pipeline-walkthrough files:**
Query events from the central DB:
```bash
python3 -c "
from pathly_orchestrator.db import get_db; import json
conn = get_db()
rows = conn.execute(\"SELECT event_type, payload FROM fsm_events WHERE feature=? ORDER BY seq\", ('<feature>',)).fetchall()
for etype, p in rows:
    print(json.dumps({'type': etype, **json.loads(p or '{}')}))
"
```
Fill and write the three templates from `{{TEMPLATES_DIR}}/pipeline-walkthrough/` to `pathly/pipeline-walkthrough/[feature]/`:

- `01-PIPELINE-FLOW.md` — FSM state sequence, conversation traces, feedback loops.
  Replace `{{FSM_STATES}}` with ordered STATE_TRANSITION `to` values;
  `{{CONVERSATION_TRACES}}` with AGENT_DONE events grouped by conversation;
  `{{FEEDBACK_LOOP_TABLE}}` with RETRY events or `| — | 0 | — | — |` if none.
- `02-TOKEN-USAGE.md` — per-agent token/cost breakdown from AGENT_DONE events.
  If all `cost_usd == 0.0`: replace cost/token columns with "not captured".
  Set `{{TOTAL_SPAWNS}}` to count of AGENT_DONE events.
- `03-ARTIFACT-MAP.md` — feedback file archive from `pathly/pipeline-walkthrough/[feature]/artifacts/`
  and source files changed (`git diff --name-only` against main branch).

Use today's date for `{{DATE}}`, `git branch --show-current` for `{{BRANCH}}`,
first HUMAN_RESPONSE value for `{{USER_INTENT}}` (or "not recorded").
If no DB events exist for the feature, write all three files with placeholders → "not recorded".

- Transition state → DONE.

Print:
```
[Stage 5 — Retro complete]
Pipeline complete. RETRO.md written to pathly/plans/[feature]/.
Pipeline walkthrough written:
  pathly/pipeline-walkthrough/[feature]/01-PIPELINE-FLOW.md
  pathly/pipeline-walkthrough/[feature]/02-TOKEN-USAGE.md
  pathly/pipeline-walkthrough/[feature]/03-ARTIFACT-MAP.md
Lessons appended to LESSONS_CANDIDATE.md (if any were extracted).
Feature '[feature]' is DONE.

To promote lessons to active memory: route to lessons
```

Route back to `team [FEATURE]`. (Orchestrator reads state DONE and stops.)
