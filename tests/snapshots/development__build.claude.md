# build

This is the canonical, tool-agnostic Pathly behavior for the build workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography**, **Completion report**, **Sub-agent spawning
> rules**, and **Live progress logging** — are composed in below from fragments. This body
> covers only the interactive build-workflow specifics.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Parse `$ARGUMENTS`: the first word is the **plan folder name** (FEATURE), and if a second word "auto" **or "fast"** is present, that signals non-interactive auto-flow mode. For example, `refactor-main auto` or `refactor-main fast` → plan = `refactor-main`, auto mode = true.

## Feature detection

If the first word of `$ARGUMENTS` is a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/features/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/features/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/features/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 1: Pre-flight check

Run `git status` (without -uall flag).

- **If working directory is clean:** Proceed to Step 2.
- **If there are uncommitted changes:** STOP. Report to user:
  ```
  Working directory is not clean. Found uncommitted changes:
  [list modified files]

  Each conversation must start from a known state. Options:
  (a) Commit current changes first
  (b) Stash them: git stash
  (c) Proceed anyway (not recommended)
  ```
  Wait for user decision before continuing. In auto-flow mode, stop immediately.

## Context gathering — three-phase builder

For non-trivial conversations (touches multiple files or an unfamiliar area), run a three-phase
build before Step 5. The NEEDS_CONTEXT contract and parallel-scout mechanics are defined in the
Scout choreography fragment; wrap each phase with `log-phase` as shown:

**Phase 1 — Analyze:**
log-phase PHASE_START analyze

Spawn `builder` with `phase: analyze` prepended to the conversation prompt:
```
phase: analyze
[conversation prompt]
```
Parse the `## NEEDS_CONTEXT` block it returns. If the block says `none`: skip Phase 2.

log-phase PHASE_DONE analyze

**Phase 2 — Scout (if NEEDS_CONTEXT has entries):**
log-phase PHASE_START scout

Run the Scout choreography with `ROLE: builder`. Use the returned compressed summary as Scout Findings.

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned)

**Phase 3 — Implement (Step 5):**
log-phase PHASE_START implement

Spawn `builder` with `phase: implement`, injecting findings:
```
phase: implement
## Scout Findings
[compressed summary — or "none" if Phase 2 was skipped]

[original conversation prompt]
```

**When to skip Phase 1:**
- Nano tasks (≤ 2 files, context already fully described in the prompt)
- Continuation conversations where prior scout findings are still valid

**If scouts return conflicting findings:** factual conflict → spawn one more targeted scout to verify; architectural conflict → write `DESIGN_QUESTIONS.md [ARCH]` and stop.

## Step 2: Locate the plan folder

Find the plan folder at `pathly/features/$PLAN/`. If it doesn't exist, list all `pathly/features/*/` folders and ask which one the user meant.

## Step 3: Determine the work source

The **board task DAG is the authoritative work list.** Query it:
```
GET http://127.0.0.1:8765/comms/tasks?feature=$PLAN&scope=$PLAN&ready=true
```

- **Board reachable with ready tasks →** drain the DAG (Step 4.6). Each task's `text` is a
  self-contained builder prompt (what to build · Files · Done when); its `artifact_path` points
  at plan context.
- **Board unreachable or no DAG (older plans / offline) →** fall back to
  `pathly/features/$PLAN/IMPLEMENTATION_PLAN.md`. Build the next `## Phase N` whose `Done when:`
  is not yet satisfied in the repo (use the live repo state to find the next unbuilt phase). There
  is no per-conversation plan file — the plan's `## Phase N` sections are the work list.

## Step 4: Confirm scope

Report to the user before starting:

```
## Next: [board task <id> — title | IMPLEMENTATION_PLAN.md Phase N — title]
- Scope: [files from the task text, or the phase `File:` fields]
- Verify: [command]
```

## Step 4.5: Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

## Step 4.6: Board task DAG (preferred work source)

If this feature has a board task DAG, it is the **authoritative** work list — drain it
(each task's `text` is the builder prompt; the DAG replaces the legacy conversation model):

1. `GET http://127.0.0.1:8765/comms/tasks?feature=<feature>&scope=<feature>&ready=true`
2. **If the list is non-empty, drain it** (do NOT also run Step 5's conversation prompt):
   a. Pick a ready task and claim it:
      `POST /comms/tasks/claim` with `{"message_id":"<id>","run_id":"build"}`.
      If `claimed` is false another worker took it — re-fetch and pick another.
   b. Implement that task from its `text` (a self-contained builder prompt — what to
      build · Files · Done when) plus its `artifact_path` for plan context. Verify-before-edit
      (Step 5.0), stay strictly in the task's scope, no silent refactoring.
   c. On success: `POST /comms/tasks/complete` with `{"message_id":"<id>","feature":"<feature>"}`.
      On unrecoverable failure: `POST /comms/tasks/fail` with `{"message_id":"<id>","reason":"<short>"}`.
   d. Re-fetch (step 1). Repeat until the ready list is empty, then **skip Steps 5–6 and go
      to Step 7**.
3. **If the list is empty or the endpoint is unreachable**, fall through to Step 5 and build the
   next unbuilt `## Phase N` from `IMPLEMENTATION_PLAN.md` (the offline fallback from Step 3).

## Step 5: Implement

Execute exactly what the work item specifies (the board task `text`, or the IMPLEMENTATION_PLAN.md phase in the offline fallback):

0. **Verify before edit** — before touching any file, glob or read the live repo to confirm every path the work item names exists and matches reality. If any path is wrong, stale, or missing: correct it and note the discrepancy. Do not proceed with a path that cannot be found.
1. Read each file that will be modified
2. Make changes following the work item's specifications exactly
3. Follow all project conventions from the project's guidance and rule files.
4. Stay strictly within the work item's scope — do NOT touch files outside the listed scope
5. **No silent refactoring**: do not rename, reformat, or clean up anything outside what the work item explicitly requires

## Step 6: Verify

Run the verify command from the work item (the task text, or the phase's `Verify:` field).

If verification fails, fix the issues before proceeding. If the fix requires out-of-scope changes, STOP and report:
```
Verification failed. The fix requires changes to [file] which is outside this conversation's scope.
Options: (a) expand scope, (b) rollback with git checkout and retry
```

Attempt up to 2 fixes. If still failing, stop and report.

log-phase PHASE_DONE implement

## Step 7: Report completion

After successful verification, report:

```
## Completed: [board task <id> | Phase N] — [title]
- Files modified: [list]
- Verification: passed
```

Do NOT commit — the orchestrator (`/pathly team`) commits after the reviewer passes. Board task status is closed by the Step 4.6 drain loop or by the orchestrator; there is no per-conversation progress file to update.

## Emitting progress notes

During long-running work, POST progress notes to the FSM so the user can see activity in the Studio Monitor:

```bash
curl -s -X POST http://127.0.0.1:8765/record_phase_summary \
  -H "Content-Type: application/json" \
  -d "{\"feature\": \"<feature>\", \"agent\": \"builder\", \"text\": \"<short note>\", \"conv\": <N>}"
```

Replace `<N>` with the current conversation number (e.g. `2`). Omit `conv` if the conversation number is unknown.

Call this at:
- After completing each conversation's implementation
- After tests pass
- Before starting a large multi-file refactor

If `PATHLY_PROJECT_ROOT` is set in the environment, omit `project_root` from the body — the server reads it from the env var. If the endpoint is unreachable or returns non-200, log a one-line warning and continue. Never abort work because a progress note failed.

## Exit contract

After successful verification, report completion to the FSM:

```bash
pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>
```

The FSM computes the next state (REVIEWING) from transition_rules and writes `STATE.json` automatically.

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Step 4.5.

**Auto-chain (fast/auto mode only):** If auto-flow mode is active and verification passed, after `log-agent-done` completes invoke the `review` skill with `<feature> <N>` (e.g. `pathly-observability 2`). If verification failed, do NOT chain — stop and report.

In non-auto mode: do not invoke any other skill. The orchestrator reads the FSM state (via DB) and decides what comes next.

## Edge Cases

- **All tasks / phases done**: Report "Plan $PLAN is already COMPLETE."
- **Board unreachable**: Fall back to reading IMPLEMENTATION_PLAN.md directly for the next unbuilt phase (Step 3).
- **Blocked task**: Report the blocker and stop.

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

## Build discipline — the laziest solution that survives review

Run this AFTER you understand the problem, never instead of it. Trace the real flow
end to end first — every file the change touches — then climb. Laziness shortens the
solution, never the reading; a small diff in the wrong place is a second bug.

**The ladder — stop at the first rung that holds.** The highest working rung wins.

1. **Does this need to exist at all?** Speculative need → skip it, say so in one line. (YAGNI)
2. **Already in this codebase?** A helper, type, util, or pattern a few files over → reuse it. Re-implementing what already exists is the most common slop — the scout phase exists to find it, so use those findings before you write.
3. **Standard library does it?** Use it. Name the function.
4. **Native platform feature covers it?** DB constraint over app code, CSS over JS, a built-in over a new dependency.
5. **An already-installed dependency solves it?** Use it. Never add a new dependency for what a few lines do.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

**Bug fix = root cause, not symptom.** A report names a symptom. Before you edit, find
every caller of the function you're about to touch (prefer the code-graph / LSP tools —
`impact` / `callers`). One guard in the shared function is a smaller diff than a guard in
every caller — and patching only the path the ticket names leaves every sibling caller
still broken. Fix it once, where all callers route through.

**House rules are the binding constraint — laziness never overrides them.** The ladder
decides how *small* the change is; the project conventions file (CLAUDE.md and any linked
rules) decides which changes are *valid* — layer/dependency direction, file-size limits,
module boundaries, and the frontend component-folder layout. "Simplest" always means
"simplest that still obeys the house rules." When the two pull apart, the house rules win
and you note the tension in one line — never silently break a documented contract to save
a line.

**Mark deliberate shortcuts with a `ponytail:` comment.** A shortcut with a known ceiling
names the ceiling and the upgrade trigger — `# ponytail: global lock, per-account locks if
throughput matters`. Simple reads as intent, not ignorance, and the marker turns a silent
deferral into a tracked one instead of "later means never". This is the one exception to
"default to no comments": a `ponytail:` marker is a WHY, not a WHAT.

**When NOT to be lazy.** Never simplify away input validation at trust boundaries, error
handling that prevents data loss, security measures, accessibility basics, or anything the
task explicitly asked for. Non-trivial logic (a branch, a loop, a parser, a money/security
path) leaves ONE runnable check behind — the smallest thing that fails if the logic breaks
(an `assert`-based self-check or one small `test_*`), no frameworks. Trivial one-liners need
no test; YAGNI applies to tests too.

Keep the report shorter than the diff. Every paragraph defending a simplification is
complexity smuggled back in as prose — the exception is explanation the task explicitly
asked for (a walkthrough, per-phase notes), which is the deliverable, not debt.

## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

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
