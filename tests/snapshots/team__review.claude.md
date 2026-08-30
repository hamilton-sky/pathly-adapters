# team/review

Stage 3b — Review. Invoked by the `team` orchestrator when FSM state is REVIEWING.
Runs reviewer for the current conversation, handles feedback loops, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`. Conv N is the most recent BUILDING work item —
the board task that was just built and claimed for review.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the REVIEWING-stage specifics.

## Role

**Stage orchestrator: Reviewing**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `<feature_path>/STATE.json` by the FSM server (the skill never writes STATE.json directly).

- **Log event:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type': 'FILE_CREATED', 'file': '<filename>', 'ts': '<iso-timestamp>'})"`
- **Log retry:** Same pattern with `{'type': 'RETRY', 'key': 'conv-N:FILE.md', 'ts': '<iso-timestamp>'}`.
- **Check retry count:** `python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`
- **Log human response:** Same pattern with `{'type': 'HUMAN_RESPONSE', 'value': '<value>', 'ts': '<iso-timestamp>'}`.
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (REVIEWING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze changes | `reviewer` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: reviewer` |
| Phase 3 — Review | `reviewer` (phase: review) |
| Fix architectural violations | `architect` |
| Fix implementation violations | `builder` |

## Rigor gate

- `lite`: reviewer runs once after the **final** builder conversation, unless any of these apply:
  feedback files exist, risky files were touched, or user preference requires per-conversation review.
  If this is not the final conversation and none of those conditions apply → skip directly to Advance.
- `standard` or `strict`: reviewer runs after **every** builder conversation.

log-phase PHASE_START review

## Phase 0 — Record review start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `REVIEW_START`.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `reviewer` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Conv N of [feature] — scan the diff to identify what context you need before reviewing.
Run: git diff HEAD~1 HEAD
Read <feature_path>/ARCHITECTURE_PROPOSAL.md if it exists.
List what you need — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: CLAUDE.md, .claude/rules/, <feature_path>/ARCHITECTURE_PROPOSAL.md | question: what architectural rules and coding conventions apply to the changed files?

Output `none` if the default rules scout above is sufficient.
```
If the block is `none`, use only the default rules scout in Phase 2.

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: reviewer`. Compress all findings into a short summary for Phase 3.

log-phase PHASE_DONE scout

## Phase 3 — Review

log-phase PHASE_START review

**Spawn** `reviewer` with `phase: review` and scout findings injected:
```
phase: review
Review the changes from conversation N of [feature].
Run: git diff HEAD~1 HEAD (or git diff --staged if not yet committed).

## Applicable Rules and Context (from pre-review scout)
[compressed findings]

If the task being reviewed has `context_refs`, for each `{artifact, anchor}` call:
  GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>
and read the returned `text` field (the full advisory spec — edge cases / happy flow
for the phase the builder implemented). The `summary` is a pointer, not the spec —
read `text`. These are the same refs the builder hydrated; review against the same spec.

Check against these rules and <feature_path>/ARCHITECTURE_PROPOSAL.md. Classify each
violation by ROOT CAUSE and write it into the matching file (see Feedback protocol —
Root-cause classification for the full tag ⇄ file ⇄ role table):
- Requirement/scope gap: <feature_path>/feedback/REQUIREMENT_GAP.md
- Plan/phasing/task-DAG problem: <feature_path>/feedback/PLAN_FEEDBACK.md
- Architectural violation: <feature_path>/feedback/ARCH_FEEDBACK.md
- UI/UX/design-system violation: <feature_path>/feedback/DESIGN_FEEDBACK.md
- Implementation defect (default): <feature_path>/feedback/REVIEW_FAILURES.md
Use the shared feedback protocol formats. One review with violations from two root causes
writes TWO files, not one file with two tags.
If all clear: report PASS.
```

log-phase PHASE_DONE review

## Feedback routing after reviewer

Apply the Feedback protocol retry-count guard before routing each file (escalate to
HUMAN_QUESTIONS.md when the retry limit is exceeded). Route the HIGHEST-PRIORITY open
file first (see Feedback protocol — priority order): `REQUIREMENT_GAP.md` >
`PLAN_FEEDBACK.md` > `ARCH_FEEDBACK.md` > `DESIGN_FEEDBACK.md` > `REVIEW_FAILURES.md`.

### If `REQUIREMENT_GAP.md` exists

After the retry guard, **spawn** `po`:
```
Read <feature_path>/feedback/REQUIREMENT_GAP.md.
Correct <feature_path>/USER_STORIES.md so the acceptance criteria/scope match the failure.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/REQUIREMENT_GAP.md when resolved.
Report: what changed in the requirement.
```
After po resolves: log file deleted for REQUIREMENT_GAP.md.
Return. Orchestrator determines next state from transition_rules.

### If `PLAN_FEEDBACK.md` exists (no `REQUIREMENT_GAP.md`)

After the retry guard, **spawn** `planner`:
```
Read <feature_path>/feedback/PLAN_FEEDBACK.md.
Correct the phasing/task DAG in <feature_path>/IMPLEMENTATION_PLAN.md.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/PLAN_FEEDBACK.md when resolved.
Report: what changed in the plan.
```
After planner resolves: log file deleted for PLAN_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `ARCH_FEEDBACK.md` exists (no `REQUIREMENT_GAP.md`/`PLAN_FEEDBACK.md`)

After the retry guard, **spawn** `architect`:
```
Read <feature_path>/feedback/ARCH_FEEDBACK.md.
Redesign the affected architecture in <feature_path>/ARCHITECTURE_PROPOSAL.md,
or <feature_path>/IMPLEMENTATION_PLAN.md for lite plans without ARCHITECTURE_PROPOSAL.md.
If phases need to change, update IMPLEMENTATION_PLAN.md.
Delete <feature_path>/feedback/ARCH_FEEDBACK.md when resolved.
Report: what changed in the design.
```
After architect resolves: log file deleted for ARCH_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `DESIGN_FEEDBACK.md` exists (no higher-priority file above)

After the retry guard, **spawn** `designer`:
```
Read <feature_path>/feedback/DESIGN_FEEDBACK.md.
Correct the UI/UX design system in <feature_path>/DESIGN.md.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/DESIGN_FEEDBACK.md when resolved.
Report: what changed in the design system.
```
After designer resolves: log file deleted for DESIGN_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `REVIEW_FAILURES.md` exists (no root-cause file above)

After the retry guard, **spawn** `builder`:
```
Read <feature_path>/feedback/REVIEW_FAILURES.md.
Fix each violation listed. Do not change anything outside the listed violations.
Delete <feature_path>/feedback/REVIEW_FAILURES.md when all fixed.
```

**Guard — zero-diff stall check** (before re-spawning reviewer):
```bash
git diff HEAD -- . ":(exclude)pathly/features/"
```
- If command fails: skip check, print `[FSM WARNING] git diff failed — skipping zero-diff check`.
- If output is **empty** (no code changed):
  Write `<feature_path>/feedback/HUMAN_QUESTIONS.md`:
  ```
  [STALL] Conversation N — builder and reviewer in zero-diff loop.
  Builder claimed to fix REVIEW_FAILURES.md but no code changed.
  Human decision required: accept as-is, override the rule, or rewrite the conversation scope.
  ```
  Log `{"type": "NO_DIFF_DETECTED", "ts": "<iso-timestamp>"}` via `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'NO_DIFF_DETECTED','ts':'<iso-timestamp>'})"`.
  Stop: "Zero-diff loop detected for Conv N. Escalated to HUMAN_QUESTIONS.md."
- If output is **non-empty**: re-run from Phase 1 — Analyze above.

### If no feedback files — PASS

**Write `<feature_path>/REVIEW.md`** with this exact content (first line must be exact):
```
RESULT: PASS
Reviewed: conversation N — <one-sentence summary of what was reviewed and the verdict>
```
The first line **must** be `RESULT: PASS` verbatim (case-sensitive, no leading whitespace). This is the
review-pass artifact the `REVIEWING → TESTING` gate (`verify_gate`) checks — without it the flow cannot
advance to testing. (Mirror of the builder's `VERIFY.md`.)

Then run the Completion report with `agent: reviewer`, `result: PASS`, using `REVIEW_START` from Phase 0.

## Advance

If not autoFlow — pause:
```
[Stage 3 — Conversation N complete + reviewed]
Reviewer: PASS. Commit your changes now.
Reply 'continue' for the next conversation, or 'stop' to pause here.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

The board task's status is already managed (completed in BUILDING, re-opened on review failure) —
there is no per-conversation progress file to mark.

**Write-or-delete transition artifacts:**
- If reviewer PASSED (no REVIEW_FAILURES.md written this run): `REVIEW.md` (RESULT: PASS) was written above — keep it,
  and delete `<storage_path>/feedback/REVIEW_FAILURES.md` if it exists.
- If reviewer FAILED (REVIEW_FAILURES.md written this run): keep it, and **delete any stale `<feature_path>/REVIEW.md`**
  from a previous pass — a failing review must never leave a passing artifact that would wave the flow through the gate.

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

## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

**Reach it whichever way your tools allow — check your own tool list, don't assume:**
- If you have the **MCP code-tools** (`mcp__codebase-memory-mcp__{search_graph,query_graph,trace_path,
  get_architecture}` and/or `mcp__serena__{find_symbol,get_symbols_overview,find_referencing_symbols}`),
  **call them directly** — they ARE the graph + LSP the `op`s below describe (`symbol` → `find_symbol`;
  `callers`/`impact` → `query_graph`/`trace_path`; whole-file/arch structure → `get_symbols_overview`/
  `get_architecture`). No Bash needed — this is how the no-Bash roles reach the graph.
- If you have **Bash**, use the HTTP proxy + CLI fallback below.
- A few roles have **both** — prefer the MCP tools for one symbol, the proxy for a broad pattern sweep.

```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" -d '{
  "op": "symbol",
  "target": "<file path OR symbol name>",
  "role": "<your-role>",
  "scope": "<feature>",
  "engine": "both" }'
```

- `op` — `symbol` (definition + signature) · `callers` (who calls it) · `impact` (what a change to
  it touches) · `chain` (call path between two symbols) · `context` (surrounding structure) ·
  `pattern` (find a code pattern). Your `role` gates which ops you may use.
- `engine` (optional) — which backend answers: `graph` (whole-repo code graph — breadth, needs
  indexing) · `lsp` (Serena/LSP — precise, always-fresh, no index; the first query per project pays
  a ~1-min warm-up, then it's fast) · `both` (merge graph + LSP). Omit to use the server's configured
  default. Prefer `lsp` or `both` right after edits, since the graph can lag recent changes.
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

**2. Advisory board POST (skip-if-down).** Mirror the artifact to the board so other agents
see it without opening the file. If the server is unreachable (connection refused / non-200),
skip silently — the on-disk `<out_path>` file is the source of truth, and the supervisor's
artifact reconciliation attaches it to the board from the FSM's own record after the stage.
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

3. Compute a **fallback** `cost_usd` from `total_tokens` and `model` (80/20 input/output split).
   This is ONLY a fallback: Pathly's spawn gate overrides it with the CLI's real cost when the run
   reports one (claude's `total_cost_usd`) or prices codex/agy centrally from tokens (`db/pricing.py`).
   **Never invent a cost for a non-claude model** — leave `other/unknown` at `0.0` and let the gate
   price it. Current rates:

   | Model prefix | Input $/MTok | Output $/MTok |
   |---|---|---|
   | `claude-opus-4` | 5.00 | 25.00 |
   | `claude-sonnet-4` | 3.00 | 15.00 |
   | `claude-haiku-4` | 1.00 | 5.00 |
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
  'run_id': '<run_id>',
  'category': '<run_category>',
  'board_scope': '<feature>',
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

# Fallback: write via eventlog (DB-primary; EVENTS.jsonl is a DB->disk export now, not an agent write)
if not _written:
    try:
        from pathly_orchestrator.eventlog import append_event as _ae
        _ae('<feature_path>', event)
        print('AGENT_DONE written to DB (fallback)')
    except Exception as _exc:
        # Soft failure only - the DB is the single authority and event_mirror.py exports
        # EVENTS.jsonl DB->disk, so an agent must NOT append to EVENTS.jsonl directly.
        print(f'AGENT_DONE could not be written to the DB (soft-fail, not mirrored to disk): {_exc}')
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

`<feature>`, `<feature_path>`, and `<run_id>` are pre-substituted by the runner — use the values as
written. (`<run_id>` keys this AGENT_DONE to its spawn so the gate's real-cost BILLING_UPDATE folds
onto it exactly instead of orphaning; if it is still literally `<run_id>`, this is an interactive run
with no gate billing, and the fold falls back to the agent/conversation match.)

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

Priority order (highest first, enforced by the flow's `feedback_priority`): `HUMAN_QUESTIONS.md` ›
`BLOCKED_ON_HUMAN.md` › `REQUIREMENT_GAP.md` › `PLAN_FEEDBACK.md` › `ARCH_FEEDBACK.md` ›
`DESIGN_FEEDBACK.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`. Other feedback files
(`DESIGN_QUESTIONS.md`, `IMPL_QUESTIONS.md`, `ACCEPTANCE_QUESTION.md`, `REFLECT_CRITIQUE.md`, …)
route after every listed file, in the flow's `feedback_routing` declaration order.

When you write a feedback file, use the shared feedback protocol formats and then report blocked.
The orchestrator routes the highest-priority open file to the responsible agent, one at a time,
before advancing.

### Root-cause classification — tag ⇄ file ⇄ role

Classify each failure by ROOT CAUSE and write it into the matching file — the filename IS
the routing (`route_feedback` matches on filename, not content). One failure with two
causes is TWO files, not one file with two tags.

| Tag | Feedback file | Routed role | That role corrects |
|---|---|---|---|
| `[REQ]` | `REQUIREMENT_GAP.md` | `po` | `USER_STORIES.md` (acceptance criteria / scope) |
| `[PLAN]` | `PLAN_FEEDBACK.md` | `planner` | `IMPLEMENTATION_PLAN.md` (phases / task DAG) |
| `[ARCH]` | `ARCH_FEEDBACK.md` | `architect` | `ARCHITECTURE_PROPOSAL.md` |
| `[DESIGN]` | `DESIGN_FEEDBACK.md` | `designer` | `DESIGN.md` |
| `[IMPL]` | `REVIEW_FAILURES.md` / `TEST_FAILURES.md` | `builder` | source code (default) |

A routed non-builder role fixes ONLY its own artifact, then either hands off to the builder
(append an `[IMPL]` item to `REVIEW_FAILURES.md`) or, if the fix was decision-only, deletes
its feedback file and lets the re-review gate re-verify — see that role's fix-mode
instructions, injected automatically whenever it is routed a feedback file.

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
    "run_id": "<run_id>",
    "stage": "<CURRENT_STATE>"
  }'
```

> Always include `"run_id": "<run_id>"` — it correlates your post to THIS run so it shows on the
> run's Pipeline **Board** tab and streams there **live** (the server tees run_id-tagged posts onto
> the per-run event feed) instead of the tab waiting on its poll.

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
    "run_id": "<run_id>",
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
    "run_id": "<run_id>",
    "stage": "<CURRENT_STATE>"
  }'
```

Rules:
- Always state your fallback assumption in `text` — the question is advisory, not a gate.
- 2–4 options, each with a one-line `description` of its consequence.
- One question per genuinely-open decision; do not turn routine work into questions.
- The human answer arrives via `/comms/answer`; you read it from the injected board context
  on your next turn. Do not poll.

## Pulling context from the Board Catalog

Your prompt's board context already pushes you the curated channels — governance,
the task's referenced sections, and semantic matches. When the task needs more than
those, you may **pull** additional artifacts from the board catalog. You are scoped to your
own board, so this is safe and bounded — you cannot see another feature's artifacts.

The **Catalog** block in your context lists the top artifacts inline (path · type · summary).
Read that first and pull only the section you actually need — do not refetch the references,
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
- **Don't refetch references** — they are already in your prompt.

## Searching the board

Your prompt's board context was assembled from ONE query the runner wrote for you — it
embedded your task description and took the top few matches per tier. That is a good first
guess, but it is a guess: it was computed before you read the task, and it cannot know the
term you are about to trip over.

When it comes up short, **ask the board yourself, in your own words**. This is the same
hybrid (keyword + semantic) index the injected context came from — you are re-querying it
with a better question, not reading a different store.

### When to search

Search when the answer plausibly already exists on the board and you do not have it:

- The injected context is thin, or it matched your task's topic but not the part you are
  actually stuck on.
- You hit a term, constraint, or name that reads like a prior decision you were not shown.
- You are about to make a choice someone may already have made — search before deciding,
  not after.

Do **not** search:

- Before reading what you were already given. The pushed channels come first, always.
- To re-fetch a reference or catalog entry that is already in your prompt.
- More than a few times for one task. Two or three targeted queries is a working session;
  ten is a sign you should proceed with what you have and say what was missing.

### How to search

```bash
curl -s -X POST http://127.0.0.1:8765/comms/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "<what you actually want to know, in plain words>",
    "feature": "<feature>",
    "board": "<board>",
    "scope": "<feature>",
    "k": 5
  }'
```

- `query` — a phrase, not a keyword. `"why does the runner spawn codex with null stdin"`
  beats `"codex stdin"`: the semantic arm matches meaning, so a fuller question ranks better.
  Capped at 512 characters.
- `k` — how many results (default 5, max 50). Start at 5; raise it only if 5 came back all
  relevant and you need more of the same.
- `mode` — optional: `hybrid` (default, use this), `keyword` for an exact literal string,
  `semantic` when you want meaning-matches only.
- `feature` — always your own `<feature>`. The route requires it, but it is only a fallback:
  `board` + `scope` are what actually select which board is searched.

### Which boards you may search

<search_tiers>

Those are the tiers this run reads, and they are the tiers you may query — one `board` +
`scope` pair each. Pass a pair **exactly as written above**: the scope is a different shape per
tier (a feature board keys by its slug, the project board by the project root path, the global
board by the literal `global`), and a mismatched pair is not an error — it returns `[]`, which
reads exactly like "the board knows nothing". Copy the pair rather than reconstructing it.

The default query above is your own board. Widen to another listed tier when the thing you are
missing is plainly not local — a cross-cutting decision, a convention, a lesson from another
feature. A tier that is NOT listed is off for this run: its board-scope setting says this agent
does not read it, and searching around that is not your call. If nothing is listed, do not
search at all.

### Reading the results

The response is a JSON array of board messages, best-first. Per result:

- `text` — the message. This is the content; read it.
- `_match_source` — `keyword` (a literal match) or `semantic` (a meaning match). A keyword
  hit is a stronger signal that you found the exact thing you named.
- `_distance` — cosine distance on semantic hits, lower is closer. Absent on keyword hits.
- `type` — `decision` and `constraint` outrank `discovery` and `status`: a decision binds
  you, a discovery merely informs you.

**An empty array means the board genuinely has nothing** — results are never padded with
recent messages, so `[]` is a real answer, not a failure. Take it at face value, stop
searching for that thing, and proceed. If what you needed was missing, say so in your
output; that gap is itself worth recording.

### Rules

- **Search reads, it never writes.** Finding something does not mean re-posting it — it is
  already on the board. Post only what YOU produced.
- **A search result is context, not authority.** Governance in your prompt still wins, and
  your own output file remains the source of truth for your work.
- **Advisory + skip-if-down.** If the server is unreachable or returns non-200, skip
  silently and proceed from the context you already have. Searching never blocks your work.
