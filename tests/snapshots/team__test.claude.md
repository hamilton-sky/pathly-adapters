# team/test

Stage 4 — Test + Fix Loop. Invoked by the `team` orchestrator when FSM state is TESTING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> and **Live progress logging** — are composed in below from fragments. This body covers only
> the TESTING-stage specifics.

## Role

**Stage orchestrator: Testing**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `<feature_path>/STATE.json`.

- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>", "ts": "<iso-timestamp>"}`.
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Phase 0 — Record test start time

Run: `python -c "import time; print(int(time.time()))"` and note the integer as `TEST_START`.

## Pre-gate

**Board task DAG.** Check whether this goal/feature has a board DAG:
```
curl -s "http://127.0.0.1:8765/comms/tasks?feature=[feature]&scope=[feature]"
```
If the response is a non-empty list, the DAG is the authoritative work list — you test the whole
goal ONCE, after every task is built and reviewed. Every task must be `task_status: done`. The
FSM's `require_tasks_done` gate already enforces this on entry to TESTING, so a stray incomplete
task means something bypassed the gate — stop and report:
```
Not all tasks are complete. Route to team <feature> build first. Incomplete: <task titles>
```

When all work is DONE: log to central DB via `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'IMPLEMENT_COMPLETE','ts':'<iso-timestamp>'})"`. Confirm state is TESTING in STATE.json.

## Subagents (TESTING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze needs | `tester` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: tester` |
| Phase 3 — Test | `tester` (phase: test) |
| Fix failing criteria | `builder` |

## Rigor depth

- `lite`: testing may be limited to the verify commands and directly relevant checks from the plan.
- `standard`: tester verifies all acceptance criteria before retro.
- `strict`: tester must map every acceptance criterion to PASS / FAIL / NOT COVERED. Cannot proceed with NOT COVERED items.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `tester` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Read <feature_path>/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: test directories, source files touched | question: what test patterns, fixtures, and coverage gaps exist for the changed files?

Output `none` if the default test-context scout above is sufficient.
```
If the block is `none`, use only the default test-context scout in Phase 2.

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: tester`. Use the returned compressed summary as `## Test Context` in Phase 3.

log-phase PHASE_DONE scout

## Phase 3 — Test

log-phase PHASE_START test

Track `testRetryCount = 0`.

**Spawn** `tester` with `phase: test` and scout findings injected:
```
phase: test
Read <feature_path>/USER_STORIES.md.
Run /test to verify each acceptance criterion.

## Test Context
[compressed findings]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write <feature_path>/feedback/TEST_FAILURES.md
using the shared feedback protocol format.
```

log-phase PHASE_DONE test

## Fix loop

After tester completes — check for `TEST_FAILURES.md`:

**If `TEST_FAILURES.md` exists:**
Increment `testRetryCount`. If `testRetryCount > 2`:
Stop — "Test failures unresolved after 2 fix cycles. Manual intervention required."

Log file created for TEST_FAILURES.md.

**Spawn** `builder`:
```
Read <feature_path>/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete <feature_path>/feedback/TEST_FAILURES.md when resolved.
```
After builder resolves: log file deleted for TEST_FAILURES.md. Re-spawn tester.

**If no TEST_FAILURES.md:** all criteria pass.

## Advance

If not autoFlow — pause:
```
[Stage 4 — Test complete]
All acceptance criteria: PASS.
Reply 'done' to proceed to retro.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

**Completion + Transition:**
- If tests still failing after fix loop: TEST_FAILURES.md already exists — keep it as the feedback signal. The FSM will halt based on transition_rules.
- If all tests pass: delete `<storage_path>/feedback/TEST_FAILURES.md` if it exists.

## Record completion

After the tester passes, run the Completion report with `agent: tester`, `conversation: 0`,
`result: PASS`, using `TEST_START` from Phase 0.

Then report completion to the FSM:
```
pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
```

The FSM reads transition_rules and the feedback artifact presence to determine the next state and write STATE.json.

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

- `<feature>` — the feature slug (folder name under `pathly/features/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" -d '{
  "op": "symbol",
  "target": "<file path OR symbol name>",
  "role": "<your-role>",
  "scope": "<feature>" }'
```

- `op` — `symbol` (definition + signature) · `callers` (who calls it) · `impact` (what a change to
  it touches) · `chain` (call path between two symbols) · `context` (surrounding structure) ·
  `pattern` (find a code pattern). Your `role` gates which ops you may use.
- The response is `{ "ok": true, "result": <block-or-null>, "backend": "<name>" }`.
- **If `result` is `null`** (backend off, file not yet indexed, or path unresolved), first try the
  **direct-CLI fallback** below; then fall back to Grep/Read. Never block on it — an accelerator, not a gate.

### Direct-CLI fallback (proxy returned null)

If `codebase-memory-mcp` is on the PATH, query its pre-built code graph directly — this works in
headless runs and covers cases the proxy misses (e.g. a file added since the last index). Resolve the
project slug once, then search:

```bash
codebase-memory-mcp cli list_projects '{}'    # pick the project whose root_path is your repo → use its "name"
codebase-memory-mcp cli search_code '{"project":"<name>","pattern":"<symbol_or_text>"}'   # ranked; note: pattern, not query
codebase-memory-mcp cli query_graph '{"project":"<name>","query":"MATCH (n) WHERE n.name=\"<sym>\" RETURN n.name, n.file_path"}'
```

`search_code` takes `pattern` (grep-like over the graph); `query_graph` runs Cypher (callers/callees,
call paths, impact). If the binary is absent or returns nothing, fall back to Grep/Read.

Use it **before** editing an unfamiliar symbol (check `callers` / `impact` so you don't break a
caller) and whenever a task names a symbol you haven't located yet (`symbol`). Prefer one targeted
query over a broad Grep sweep.

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

---

## Completion report (AGENT_DONE) — your FINAL action

`AGENT_DONE` is the authoritative signal the supervisor reads to end this stage, and the runner's
early-advance acts on it the instant it appears in the central DB — it does **not** wait for your
process to exit. So this is the **last thing you do**, with NOTHING after it:

- Write it ONLY after every output file is written **and** every board write is done — including
  deliverable board state (a seeded task DAG: `type=goal` / `type=task`) and any advisory
  `artifact` / `status` / `decision` posts. Anything that writes to the board comes BEFORE this.
- If the task above lists later steps (e.g. "Post Tasks to Comms Board"), this runs **after all of
  them** — never mid-workflow. A completion report emitted early lets early-advance silently cut off
  the remaining steps, so the DAG you were supposed to seed never gets posted.
- The skill supplies only the *content* (role, result, conversation, summary, the `*_START` time);
  this fragment owns *when* (last) and *how* (below).

## Set `outcome` — success or failed (REQUIRED)

The AGENT_DONE carries an explicit `outcome` the supervisor's loop executor reads to decide
whether your task **succeeded** or **failed**. A clean process exit is **not** taken as success on
its own — you must say so. Judge honestly:

- `outcome: 'success'` — you completed the task and its acceptance/goal is met. Leave `error` empty (`''`).
- `outcome: 'failed'` — you could **not** complete it: a blocking dependency, an unmet requirement,
  a build/test you could not get to pass, or a hard limit you hit. Put the one-sentence reason in
  `error`. Still write the report — a reported failure lets the DAG block dependents loudly instead
  of draining a broken branch as "done".

When genuinely unsure between the two, prefer `failed` with an `error`: a false success hides broken
work (the costlier mistake), while a false failure only re-surfaces the task.

Write the AGENT_DONE event to the **central DB** via eventlog. This is **mandatory** — the
supervisor reads it as the authoritative result.

## Compute wall seconds

1. Compute wall_seconds: `python3 -c "import time; print(int(time.time()) - BUILD_START)"`

## Sum subagent tokens

2. Sum `total_tokens` and `tool_uses` across **ALL** subagents spawned during this stage (analyze, scouts, implement/review, and every fix/retry iteration). Parse each subagent's `<usage>` block (look for `subagent_tokens:` and `tool_uses:` lines in the tool result) and add to running totals. `duration_ms = 0` if absent.

## Estimate cost

3. Compute `cost_usd` from `total_tokens` and `model` using an 80/20 input/output token split:

   | Model prefix | Input $/MTok | Output $/MTok |
   |---|---|---|
   | `claude-opus-4` | 15.00 | 75.00 |
   | `claude-sonnet-4` | 3.00 | 15.00 |
   | `claude-haiku-4` | 0.80 | 4.00 |
   | other / unknown | — | set `cost_usd = 0.0` |

   Formula:
   ```
   in_est  = total_tokens * 0.8
   out_est = total_tokens * 0.2
   cost_usd = round((in_est / 1_000_000 * input_rate) + (out_est / 1_000_000 * output_rate), 6)
   ```

## Write the AGENT_DONE event

4. Write the event — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime, pathlib
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'MODEL_ID',
  'conversation': CONV_N,
  'result': 'DONE',
  'outcome': 'OUTCOME',
  'error': 'ERROR_REASON',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': COST_USD,
  'ts': ts,
  'schema_version': 1,
}

_written = False

# Primary path: POST to HTTP endpoint
try:
    import urllib.request, urllib.error
    body = json.dumps({
        'type': event['type'],
        'feature': '<fsm_feature>',
        'project_root': str(pathlib.Path.cwd()),
        'payload': event,
    }).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8765/runner/event',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        if resp.status == 200:
            print('AGENT_DONE written via HTTP /runner/event')
            _written = True
except Exception:
    pass  # server unreachable — fall through to local fallback

# Fallback: write via eventlog (DB-primary, EVENTS.jsonl secondary)
if not _written:
    try:
        from pathly_orchestrator.eventlog import append_event as _ae
        _ae('<feature_path>', event)
        print('AGENT_DONE written to DB (fallback)')
    except Exception as _exc:
        path = pathlib.Path('<feature_path>/EVENTS.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as _f:
            _f.write(json.dumps(event) + chr(10))
        print(f'AGENT_DONE written to EVENTS.jsonl (last resort: {_exc})')

# Always dual-write to EVENTS.jsonl as backup
path = pathlib.Path('<feature_path>/EVENTS.jsonl')
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'a', encoding='utf-8') as _f:
    _f.write(json.dumps(event) + chr(10))
"
```

## Post to activity log

5. POST to the activity log — non-blocking; skip silently if server is unavailable:

```bash
pathly-fsm-call record-activity \
  --agent "AGENT_ROLE" \
  --feature "<feature>" \
  --summary "SUMMARY_SENTENCE" \
  --conversation CONV_N \
  --model "MODEL_ID" \
  --total-tokens TOTAL_TOKENS \
  --tool-uses TOOL_USES \
  --wall-seconds WALL_SECONDS \
  --cost-usd COST_USD
```

## Placeholder reference

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`, `planner`
- `MODEL_ID` — model used in this stage (e.g. `claude-sonnet-4-6`)
- `CONV_N` — integer conversation number (0 for non-build stages like plan/review/test)
- `OUTCOME` — `success` or `failed` (see "Set `outcome`" above) — the supervisor's authoritative pass/fail signal
- `ERROR_REASON` — one-sentence failure reason when `OUTCOME` is `failed`; empty string `''` when `success`
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation
- `COST_USD` — computed in step 3

## Return to orchestrator

`<feature>` and `<feature_path>` are pre-substituted by the runner — use the values as written.

Return. The orchestrator determines the next state from `transition_rules`.

## Scout choreography (analyze → scout → compress)

The stage agent (builder / reviewer / tester) declares what context it needs *before* doing the
work, scouts gather that context in parallel, and the findings are compressed into the work prompt.

### Phase 1 — Analyze

Spawn the stage agent with `phase: analyze`. It outputs a `## NEEDS_CONTEXT` block **only** —
the list of things it must know before implementing / reviewing / testing.

NEEDS_CONTEXT format (one entry per line):
```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
```

Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2 (or use only the stage's
default scout entry, where one is defined).

### Phase 2 — Scout (parallel, max 4)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: <stage agent>` + the question
- `type: scout` → spawn `scout` with `ROLE: <stage agent>` + scope + question

After each scout/quick returns, parse its `<usage>` block (`subagent_tokens`, `tool_uses`) and
record it immediately — non-blocking, skip if server unavailable:

```bash
# For each scout that returned — replace placeholders with actual values from <usage> block
# model is claude-haiku-4-5-20251001 for scout/quick agents
pathly-fsm-call record-activity \
  --agent "scout" \
  --feature "<feature>" \
  --summary "<question truncated to 80 chars>" \
  --conversation N \
  --model "claude-haiku-4-5-20251001" \
  --total-tokens SCOUT_TOKENS \
  --tool-uses SCOUT_TOOL_USES \
  --wall-seconds 0 \
  --cost-usd SCOUT_COST_USD
```

Compute `SCOUT_COST_USD` using haiku rates (input $0.80/MTok, output $4.00/MTok) with 80/20 split.
Add each scout's `SCOUT_TOKENS` to the stage running total for the final AGENT_DONE.

Compress all returned findings into a short summary and inject it into the Phase 3 work prompt
as the stage's findings section.

---

---
## Feedback protocol

All feedback files live in `<feature_path>/feedback/`. File exists = issue open.
Absent = resolved.

Priority order (highest first): `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`ACCEPTANCE_QUESTION.md` › `IMPL_QUESTIONS.md` › `REFLECT_CRITIQUE.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

When you write a feedback file, use the shared feedback protocol formats and then report blocked.
The orchestrator routes the highest-priority open file to the responsible agent, one at a time,
before advancing.

### Guard — feedback-open check

Before spawning the stage agent, scan `<feature_path>/feedback/`. If any file exists:
1. Identify the highest-priority file using the order above.
2. Log file created for that file.
3. Route to the responsible agent (see the stage's feedback routing section).
4. When resolved and the file is deleted: log file deleted. Re-scan.
5. Only proceed when no feedback files remain.

### Guard — retry-count check (3-tier escalation)

A **failure** file (`REVIEW_FAILURES.md`, `TEST_FAILURES.md`, `SCOPE_VIOLATION.md`) routes
**upstream** as the same loop keeps failing — repeated failure usually means the
plan / design / acceptance-criteria are wrong, not the local fix:

- **Rounds 1–2** → the file's owner (the **builder**). Log retry for `conv-N:FILE.md`, route the fix.
- **Round 3** → the **upstream specialist** named in the flow's `escalation_routing`
  (e.g. `REVIEW_FAILURES → planner`, `TEST_FAILURES → po`) — the plan/criteria are the suspect.
- **Round 4+** → the **human** (the FSM returns `decision: escalate`).

You don't choose the target — the FSM's `route_feedback` resolves it from the flow's
`feedback_routing` + `escalation_routing` and the file's retry count. **Your job:** write the
failure file and report blocked; the FSM routes it to the right role. (Log retry for
`conv-N:FILE.md` so the count advances. Check it via the central DB if you need to:
`python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`)

**Clarification** requests are exempt from tiering and always go to their owner:
`IMPL_QUESTIONS.md → planner`, `DESIGN_QUESTIONS.md → designer/architect`,
`ACCEPTANCE_QUESTION.md → po` (the tester asks whether the acceptance criteria themselves are right).

---

---
## Consult a peer — get advice from another role

You are not alone in the pipeline. When you are blocked on something another ROLE owns — the
"what / why" (po), the stories or acceptance criteria (planner), the design / contracts (architect),
the UX (designer), the test strategy (tester), or a second opinion on the diff (reviewer) — you may
**consult** that role instead of guessing. A consult is advice only; it never silently advances the
pipeline or edits another role's artifacts.

**To consult, post a board question addressed to the role** so the human sees the exchange and the
answer threads onto the board:

```
POST http://127.0.0.1:8765/comms/post
{ "feature": "<feature>", "scope": "<feature>", "from": "<your role>", "to": "<role>",
  "type": "question", "text": "<ONE bounded question — and the assumption you will proceed on>" }
```

Who owns what:

| Ask… | for |
|---|---|
| po | scope, intent, success criteria — "is this the right thing to build?" |
| planner | story breakdown, acceptance criteria, ordering, rigor |
| architect | design, layers, contracts, migrations, rollback |
| designer | UX, component shape, visual + interaction states |
| tester | verification strategy, coverage, the gaps you can't see |
| reviewer | likely violations, diff quality, contract risk (advisory) |

Rules:
- Ask exactly ONE bounded question, and state the fallback assumption you will proceed on. **Never
  block** waiting for a reply — the runner/human routes the answer back asynchronously.
- A consult yields advice. If you actually need the specialist to CHANGE an artifact (not just
  advise), write the matching `feedback/<TYPE>.md` instead — see the Feedback protocol — and the FSM
  routes them to resolve it before the pipeline advances.

**When you are consulted** (a `question` whose `to` is your role): answer on the board with
`{"from": "<role>", "type": "answer", "reply_to": "<question id>", ...}` — concrete and advice-only.
Do not edit code or plan files unless that is your current stage.

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
    "board": "<board>",
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
    "feature": "<feature>", "from": "<your-role>", "type": "artifact", "board": "<board>",
    "text": "<1-2 sentence description>", "summary": "<topic map, one line per section>",
    "artifact_path": "<path to the file>", "artifact_type": "md"}'
  ```
- Never paste full file content — keep `text` to 1–2 sentences and `summary` to one line per section.
- `<board>` is set for you by the runner — it is the board **tier** your stage writes to
  (`feature` for a feature/goal run, `project` for a project decompose). Post with
  `"board": "<board>"` and your write lands on the right board. `global`-tier writes stay
  role-gated (`director`/`human`); a `feature` write is always unrestricted.

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
    "board": "<board>",
    "stage": "<CURRENT_STATE>"
  }'
```

Rules:
- Always state your fallback assumption in `text` — the question is advisory, not a gate.
- 2–4 options, each with a one-line `description` of its consequence.
- One question per genuinely-open decision; do not turn routine work into questions.
- The human answer arrives via `/comms/answer`; you read it from the injected board context
  on your next turn. Do not poll.
