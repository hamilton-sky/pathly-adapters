# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes one TODO conversation (analyze → scout → implement), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the BUILDING-stage specifics.

## Role

**Stage orchestrator: Building**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `<feature_path>/STATE.json` by the FSM after each transition.

- **Log event:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type': 'FILE_CREATED', 'file': '<filename>', 'ts': '<iso-timestamp>'})"`
- **Log retry:** Same pattern with `{'type': 'RETRY', 'key': 'conv-N:FILE.md', 'ts': '<iso-timestamp>'}`.
- **Check retry count:** `python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (BUILDING stage)

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Clarify requirement | `planner` |
| Clarify architecture | `architect` |

## Execution

log-phase PHASE_START build

### Phase 0 — Board task DAG (preferred)

Before reading PROGRESS.md, check whether this feature has a board task DAG:
```
curl -s "http://127.0.0.1:8765/comms/tasks?ready=true&feature=[feature]&scope=[feature]"
```
**If the response is a non-empty list of ready tasks, BUILD FROM THE BOARD** — the DAG is
the authoritative work list (it supersedes PROGRESS.md / CONVERSATION_PROMPTS.md). Drain it:

1. Pick a ready task. Claim it: `POST /comms/tasks/claim {"message_id":"<id>","run_id":"build"}`.
   If `claimed` is false, another worker took it — re-fetch and pick another.
2. **Spawn** `builder` with `phase: implement`, passing the task's `text` as the
   instructions (it is a self-contained builder prompt — what to build · Files · Done when)
   and reading its `artifact_path` for plan context. Execute that one task. Verify.
   - Requirement ambiguity → write `feedback/IMPL_QUESTIONS.md` (routed to planner).
   - Technical blocker → write `feedback/DESIGN_QUESTIONS.md` (routed to architect).
3. On success: `POST /comms/tasks/complete {"message_id":"<id>","feature":"[feature]"}`.
   On unrecoverable failure: `POST /comms/tasks/fail {"message_id":"<id>","reason":"<short>"}`.
4. Re-fetch ready tasks (step 0). Repeat until the ready list is empty.

When the DAG is drained, skip the conversation flow below — go straight to **Phase 3.5
(Write VERIFY.md)** and transition to review.

**If the response is empty OR the server is unreachable (connection refused), FALL BACK**
to the conversation-based build below (unchanged) — this keeps features that have no board
DAG (older plans) working exactly as before.

### Conversation fallback

Read `<feature_path>/PROGRESS.md`. Find the first conversation row with status TODO. This is Conv N.

### Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `builder` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Route to continue [feature] conversation N.
List what you need to know before implementing — output NEEDS_CONTEXT block only.
```

log-phase PHASE_DONE analyze

### Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: builder`. Use the returned compressed summary as Scout Findings.

log-phase PHASE_DONE scout

### Phase 2.5 — Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

### Phase 3 — Implement

log-phase PHASE_START implement

**Spawn** `builder` with `phase: implement`:
```
phase: implement
Route to continue [feature] in manual mode.
Execute conversation N only. Verify. Do NOT update PROGRESS.md — the orchestrator handles that after the reviewer passes.

## Scout Findings
[compressed summary — or "none" if Phase 2 was skipped]

If you hit requirement ambiguity (what should this do?): write <feature_path>/feedback/IMPL_QUESTIONS.md
If you hit a technical blocker (how is this possible?): write <feature_path>/feedback/DESIGN_QUESTIONS.md
Use the shared feedback protocol formats, then report blocked.
Report: files changed, verify result, stories delivered.
```

log-phase PHASE_DONE implement

### Feedback routing after builder

Feedback file priority, the feedback-open guard, and the retry-count guard are defined in the
Feedback protocol fragment. Route the highest-priority open file to the agent below.

**If `IMPL_QUESTIONS.md` exists** ([REQ] tagged):
**Spawn** `planner`:
```
Read <feature_path>/feedback/IMPL_QUESTIONS.md.
Answer each [REQ] question — clarify in USER_STORIES.md or CONVERSATION_PROMPTS.md.
Delete <feature_path>/feedback/IMPL_QUESTIONS.md when resolved.
```
After resolved: log file deleted for IMPL_QUESTIONS.md. Re-run Phase 3. Do not log retry.

**If `DESIGN_QUESTIONS.md` exists** ([ARCH] tagged):
**Spawn** `architect`:
```
Read <feature_path>/feedback/DESIGN_QUESTIONS.md.
Resolve each [ARCH] question — update ARCHITECTURE_PROPOSAL.md (or IMPLEMENTATION_PLAN.md for lite plans).
Delete <feature_path>/feedback/DESIGN_QUESTIONS.md when resolved.
```
After resolved: log file deleted for DESIGN_QUESTIONS.md. Re-run Phase 3. Do not log retry.

Both files can exist simultaneously. Route one at a time using the priority order. After both resolve → builder re-implements.

## Transition to review

After Phase 3 completes with no blocking feedback files:

### Phase 3.5 — Write VERIFY.md

Write `<feature_path>/VERIFY.md` with this exact content (first line must be exact):
```
RESULT: PASS
Verified: conversation N complete — <one-sentence summary of what was verified and the outcome>
```

Replace `<feature>` with the feature slug and `N` with the conversation number.
The first line **must** be `RESULT: PASS` verbatim (case-sensitive, no leading whitespace).

log-phase PHASE_DONE build

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Phase 2.5.

Return. Orchestrator determines next state from transition_rules.

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
        'feature': '<feature>',
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

## Sub-agent spawning rules

This stage runs on a host that can spawn sub-agents (Task / subagent capability).

- **Never execute work yourself** — spawn the right subagent for each step.
- Treat the FSM as a deterministic filesystem machine: read disk, process one event, emit one action.
- After every agent completes, check for feedback files before advancing.
- Spawn scouts and parallel workers up to a maximum of 4 at once.

Map each action to its subagent (the stage skill lists the exact roles for that stage):

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Review changes | `reviewer` |
| Verify acceptance criteria | `tester` |
| Clarify requirement | `planner` |
| Clarify / redesign architecture | `architect` |
| Scout context | `scout` or `quick` (with `ROLE:` set to the stage agent) |

## Pulling context from the Board Catalog

Your prompt's board context already pushes you the curated channels — 🔒 governance,
📎 the task's referenced sections, and 💡 semantic matches. When the task needs more than
those, you may **pull** additional artifacts from the board catalog. You are scoped to your
own board, so this is safe and bounded — you cannot see another feature's artifacts.

The 📚 **Catalog** block in your context lists the top artifacts inline (path · type · summary).
Read that first and pull only the section you actually need — do not refetch the 📎 references,
they are already hydrated.

### How to pull

```bash
# List what's available on your board (already permission-scoped to you)
curl -s "http://127.0.0.1:8765/comms/artifacts?board=feature&scope=<feature>"

# Read one section (omit &anchor for the whole file)
curl -s "http://127.0.0.1:8765/comms/artifacts/section?scope=<feature>&artifact=<path>&anchor=<anchor>&trail=<task_id>"
```

Read the returned `text` field — it is the authoritative section, not the `summary`.

### Rules

- **Pull narrowly.** Only fetch what the current task needs; the catalog is large by design.
- **Record what you read.** Append `&trail=<task_id>` to a section pull so the board logs the
  access — this is how the timeline shows what context each task consumed.
- **Advisory + skip-if-down.** If the server is unreachable, skip silently and proceed from the
  context you already have. Pulling never blocks your work.
- **Don't refetch 📎 references** — they are already in your prompt.
