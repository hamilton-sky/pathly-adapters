# team/retro

Stage 5 — Retrospective. Invoked by the `team` orchestrator when FSM state is RETRO.

Parse `$ARGUMENTS`: `FEATURE`.

## FSM operations

- **Report stage completion to the FSM:** `pathly-fsm-call complete-stage --flow team --topic <FEATURE> --project-root <project_root>`
  The FSM computes the next state from transition_rules and writes the DB and STATE.json mirror itself. The skill does not pick a target state or write STATE.json.

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
- Write `<feature_path>/RETRO.md` with the summary provided.
- Append any extracted lessons to `pathly/lessons/LESSONS_CANDIDATE.md` (create the directory if needed).

Parse the `<usage>` block from quick's response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Then invoke the `log-agent-done` skill with:
```json
{"agent":"quick","feature":"<fsm_feature>","conversation":0,"result":"DONE","total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>}
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

- Report completion to the FSM: `pathly-fsm-call complete-stage --flow team --topic <FEATURE> --project-root <project_root>` (FSM computes DONE via transition_rules).

Print:
```
[Stage 5 — Retro complete]
Pipeline complete. RETRO.md written to <feature_path>/.
Pipeline walkthrough written:
  pathly/pipeline-walkthrough/[feature]/01-PIPELINE-FLOW.md
  pathly/pipeline-walkthrough/[feature]/02-TOKEN-USAGE.md
  pathly/pipeline-walkthrough/[feature]/03-ARTIFACT-MAP.md
Lessons appended to pathly/lessons/LESSONS_CANDIDATE.md (if any were extracted).
Feature '[feature]' is DONE.

To promote lessons to active memory: route to lessons
```

Route back to `team [FEATURE]`. (Orchestrator reads state DONE and stops.)
