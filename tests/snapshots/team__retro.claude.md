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

- Report completion to the FSM: `pathly-fsm-call complete-stage --flow team --topic <FEATURE> --project-root <project_root>` (FSM computes DONE via transition_rules).

Print:
```
[Stage 5 — Retro complete]
Pipeline complete. RETRO.md written to <feature_path>/.
Pipeline walkthrough written:
  pathly/pipeline-walkthrough/[feature]/01-PIPELINE-FLOW.md
  pathly/pipeline-walkthrough/[feature]/02-TOKEN-USAGE.md
  pathly/pipeline-walkthrough/[feature]/03-ARTIFACT-MAP.md
Lessons appended to LESSONS_CANDIDATE.md (if any were extracted).
Feature '[feature]' is DONE.

To promote lessons to active memory: route to lessons
```

Route back to `team [FEATURE]`. (Orchestrator reads state DONE and stops.)

## Live progress logging

Each `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>` marker is a mandatory
pipeline event. When you encounter one (or an inline `Run:` bash block replacing it), execute it immediately:

Run:
```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START \
  --project-root "<project_root>"

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE \
  --project-root "<project_root>"
```

- `<feature>` — the feature slug (folder name under `pathly/plans/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Registering your output artifact

After you finish your stage work, register your primary output artifact. This runs **after**
you write your output file and **before** your completion report — so `AGENT_DONE` stays your
final act. This step never advances the pipeline: no `/complete_stage`, no `next-action`, no
FSM transition. The supervisor advances the flow once your artifact exists.

**1. Write your output file.** Write your stage's primary artifact to exactly `<out_path>`
(the runner injected this path — do not choose your own). This is the file the gate checks.

**2. Append one line to the artifact ledger.** Append a single JSON line to
`<feature_path>/ARTIFACTS.jsonl` (create the file if absent, append-only — never rewrite it):
```bash
python3 -c '
import json, os, sys, time
rec = {"role": "<agent>", "path": "<out_path>", "type": "md",
       "title": "<short title>", "summary": "<one-line gloss>", "ts": time.time()}
p = "<feature_path>/ARTIFACTS.jsonl"
with open(p, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec) + "\n")
'
```

**3. Advisory board POST (skip-if-down).** Mirror the artifact to the board so other agents
see it without opening the file. If the server is unreachable (connection refused / non-200),
skip silently — `ARTIFACTS.jsonl` and the file are the source of truth.
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{"feature": "<feature>", "from": "<agent>", "type": "artifact", "board": "feature",
       "scope": "<feature>", "text": "<1-2 sentence description>",
       "artifact_path": "<out_path>", "artifact_type": "md"}'
```

## Posting to the Comms Board

After you finish your work and write your output file(s), mirror the key finding or decision to
the comms board. This makes it visible to every other agent and to Studio **without** them having
to open your file. The board is read back into every agent's prompt automatically.

This is one-directional broadcast — you post and continue. It never blocks your work, and it is
advisory: if the FSM server is unreachable, skip it silently (your output file is the authority).

### Choose the type that fits what you produced

| What you found | type | When to use it |
|---|---|---|
| A decision the team must accept | `decision` | design choice, rigor level, scope cut, review/test PASS |
| A constraint future agents must respect | `constraint` | arch rule, API limit, known incompatibility |
| A factual discovery, no action needed yet | `discovery` | explorer finding, root cause identified |
| A violation or risk that blocks progress | `warning` | review failure, test failure, security issue |
| A completed output file | `artifact` | DESIGN.md, CONCLUSIONS.md, RETRO.md, REVIEW_FAILURES.md |

### How to post

For each finding (one post per finding — not one per file line), POST to the board. Replace
`<feature>` with the feature slug, `<your-role>` with your agent role (`reviewer`, `tester`,
`designer`, `explorer`, `builder`, `planner`, …), and `<CURRENT_STATE>` with the active FSM stage.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<your-role>",
    "type": "<type>",
    "text": "<one self-contained paragraph — what you found and why it matters>",
    "board": "feature",
    "stage": "<CURRENT_STATE>"
  }'
```

**Server availability — skip-if-down (advisory):**
If the call fails or the server is not reachable (connection refused / non-200), skip silently and
continue. The board is a convenience mirror; your output file is the source of truth. Do **not**
start the server or retry in a loop just to post.

### Rules

- One post per finding, not one per file line.
- `text` must be self-contained — other agents read this without opening your file.
- Post `warning` items **before** writing the feedback file, so Studio shows them in real time.
- Post an `artifact` **after** the file is written. Provide TWO fields so it is both readable
  and findable:
  - `text` — a real **1–2 sentence description**: what the artifact is and why it matters. NOT a
    bare label like "Design doc: X".
  - `summary` — a compact **topic map of the file's sections**: one line per heading with a short
    gloss. This is the catalog entry other agents scan, and it is embedded for **semantic
    retrieval**, so make it cover the real section topics.
  ```bash
  curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{
    "feature": "<feature>", "from": "<your-role>", "type": "artifact", "board": "feature",
    "text": "<1-2 sentence description>", "summary": "<topic map, one line per section>",
    "artifact_path": "<path to the file>", "artifact_type": "md"}'
  ```
- Never paste full file content — keep `text` to 1–2 sentences and `summary` to one line per section.
- Only `feature`-scope writes are unrestricted. `project`/`global` writes are role-gated and may
  return 403 — that is expected; keep your post at `"board": "feature"` unless you are `director`/`human`.

### What each role typically posts

| Role / stage | After writing | Post |
|---|---|---|
| `reviewer` (REVIEWING) | `REVIEW_FAILURES.md` | one `warning` per BLOCKER/MAJOR finding; one `decision` ("Review PASS") on a clean pass |
| `tester` (TESTING) | `TEST_FAILURES.md` | one `warning` per failing acceptance criterion; one `decision` ("Tests PASS") on pass |
| `designer` (DESIGNING) | `DESIGN.md` | one `artifact` summarizing the design system (stack, palette, type, key choices) |
| `explorer` (any) | `CONCLUSIONS.md` | one `discovery` per significant finding |
| `builder` (debugging) | `DEBUG_REPORT.md` | one `discovery` for the root cause; one `decision` for the chosen fix |
| `planner` (RETRO) | `RETRO.md` | one `artifact` summarizing lessons; one `decision` per accepted instruction patch |

### Asking a question (non-blocking)

When you need a human decision but must **not** block, post a `question` with 2–4 options.
You continue working on the assumption stated in `text`; if a human answers, the answer is
injected at the next `/next_action`. Never wait in a loop for the reply.

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<your-role>",
    "type": "question",
    "text": "<the question + the assumption you are proceeding with if unanswered>",
    "options": [
      {"id": "a", "label": "<option A>", "description": "<short consequence>"},
      {"id": "b", "label": "<option B>", "description": "<short consequence>"}
    ],
    "board": "feature",
    "stage": "<CURRENT_STATE>"
  }'
```

Rules:
- Always state your fallback assumption in `text` — the question is advisory, not a gate.
- 2–4 options, each with a one-line `description` of its consequence.
- One question per genuinely-open decision; do not turn routine work into questions.
- The human answer arrives via `/comms/answer`; you read it from the injected board context
  on your next turn. Do not poll.
