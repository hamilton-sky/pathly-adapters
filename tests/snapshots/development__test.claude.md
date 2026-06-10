# test

This is the canonical, tool-agnostic Pathly behavior for the standalone test workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography** and **Live progress logging** — are composed in
> below from fragments. This body covers only the standalone test-workflow specifics.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use `/test` to verify acceptance criteria for a completed feature, or to run a targeted
test pass against a specific plan folder outside the full team pipeline.

Use `team <feature> test` when running within the full pipeline (build → test → retro).

---

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/plans/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 0 — Locate the plan

Parse `$ARGUMENTS` for a plan folder name (FEATURE). If blank, use the auto-detected FEATURE above.

Read `pathly/plans/<feature>/PROGRESS.md`. If Status is not COMPLETE (or all conversations
not DONE), stop:

```
Not all conversations are DONE for <feature>. Run /build first.
```

Read `pathly/plans/<feature>/USER_STORIES.md` (required). If missing, stop:

```
No USER_STORIES.md found for <feature>. Cannot run acceptance tests without stories.
```

---

## Step 1 — Analyze (tester phase: analyze)

log-phase PHASE_START analyze

Spawn the **tester** agent with `phase: analyze`:

```
phase: analyze
Read pathly/plans/<feature>/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.
```

Parse the `## NEEDS_CONTEXT` block it returns.

log-phase PHASE_DONE analyze

---

## Step 2 — Scout (if NEEDS_CONTEXT has entries)

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: tester`. Use the returned compressed summary as
`## Test Context` (set it to `none` and skip this step if `NEEDS_CONTEXT` was `none`).

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned, or 0 if skipped)

---

## Step 3 — Test (tester phase: test)

log-phase PHASE_START test

Spawn the **tester** agent with `phase: test`:

```
phase: test
Read pathly/plans/<feature>/USER_STORIES.md.
Run the verify command(s) to check each acceptance criterion.

## Test Context
[compressed summary from Step 2, or "none"]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write pathly/plans/<feature>/feedback/TEST_FAILURES.md.
```

log-phase PHASE_DONE test

---

## Step 4 — Fix loop (if TEST_FAILURES.md exists)

Track `retryCount = 0`.

**If `TEST_FAILURES.md` exists:**

Increment `retryCount`. If `retryCount > 2`: stop —
```
Test failures unresolved after 2 fix cycles. Manual intervention required.
```

Spawn **builder**:
```
Read pathly/plans/<feature>/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete pathly/plans/<feature>/feedback/TEST_FAILURES.md when resolved.
```

After builder completes: re-run Step 3.

**If no `TEST_FAILURES.md`:** all criteria pass — proceed to Step 5.

---

## Step 5 — Report

Print the tester's full test plan output showing PASS/FAIL/NOT COVERED per criterion.

Then ask:

```
Test run complete. What next?

[1] Proceed to retro       /retro <feature>
[2] Re-run tests           /test <feature>
[3] Done — keep as record
```

---

## Rules

- **Tester + builder only** — no reviewer, no planner.
- **Tester does not fix code.** Builder handles all fixes.
- **Run before reporting.** Never claim PASS without executing the verify command.
- **Strict rigor:** all NOT COVERED criteria must be resolved before proceeding to retro.

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
