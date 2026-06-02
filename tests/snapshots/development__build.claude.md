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
1. Read `pathly/plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/plans/` folder exists or is empty: stop →
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

Find the plan folder at `pathly/plans/$PLAN/`. If it doesn't exist, list all `pathly/plans/*/` folders and ask which one the user meant.

## Step 3: Read current state

Read these files:

1. **`pathly/plans/$PLAN/PROGRESS.md`** — Find the first row in the "Conversation Breakdown" table with status **TODO**. That is the next target conversation. Also check overall Status — if COMPLETE, stop and report.

2. **`pathly/plans/$PLAN/CONVERSATION_PROMPTS.md`** — Find the section for the target conversation number. Extract:
   - The full prompt (everything inside the ` ``` ` block)
   - The verify command (from the prompt or the "Expected output" line)
   - Files touched (listed after the prompt block)

## Step 4: Confirm scope

Report to the user before starting:

```
## Next: Conversation N — [title]
- Scope: [files listed in CONVERSATION_PROMPTS.md]
- Verify: [command]
```

## Step 4.5: Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

## Step 5: Implement

Execute exactly what the conversation prompt specifies:

0. **Verify before edit** — before touching any file, glob or read the live repo to confirm every path in the conversation prompt exists and matches reality. If any path is wrong, stale, or missing: correct it and note the discrepancy. Do not proceed with a path that cannot be found.
1. Read each file that will be modified
2. Make changes following the prompt's specifications exactly
3. Follow all project conventions from the project's guidance and rule files.
4. Stay strictly within the conversation's scope — do NOT touch files outside the listed scope
5. **No silent refactoring**: do not rename, reformat, or clean up anything outside what the prompt explicitly requires

## Step 6: Verify

Run the verify command from the conversation prompt.

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
## Completed: Conv N — [title]
- Files modified: [list]
- Verification: passed
```

Do NOT update PROGRESS.md. Do NOT commit. The orchestrator (`/pathly team`) handles both after the reviewer passes.

## Exit contract

Write `pathly/plans/<feature>/STATE.json`:
```json
{"current": "REVIEWING", "feature": "<feature>", "rigor": "<rigor>", "updated_at": "<iso-timestamp>"}
```

Append to `pathly/plans/<feature>/EVENTS.jsonl`:
```
{"type": "STATE_TRANSITION", "to": "REVIEWING", "ts": "<iso-timestamp>"}
```

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Step 4.5.

**Auto-chain (fast/auto mode only):** If auto-flow mode is active and verification passed, after `log-agent-done` completes invoke the `review` skill with `<feature> <N>` (e.g. `pathly-observability 2`). If verification failed, do NOT chain — stop and report.

In non-auto mode: do not invoke any other skill. The orchestrator reads STATE.json and decides what comes next.

## Edge Cases

- **All conversations DONE**: Report "Plan $PLAN is already COMPLETE."
- **No CONVERSATION_PROMPTS.md**: Fall back to reading IMPLEMENTATION_PLAN.md directly for the next TODO phase.
- **Blocked conversation**: Report the blocker and stop.

## Live progress logging

When this skill says `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>`,
run the corresponding command below, filling in the actual feature name, agent role, and phase:

```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE
```

- `<feature>` — the feature slug (folder name under `pathly/plans/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

If `pathly-fsm-call` is unavailable or the server is not running, skip silently.
Phase logging must never block the main workflow.

## Completion report (usage parse + log-agent-done)

After the stage agent completes (Phase 3), parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Compute the `wall_seconds` fallback: run
`python -c "import time; print(int(time.time()) - <STAGE>_START)"` using the `<STAGE>_START`
integer recorded at the start of this stage.

Then invoke the `log-agent-done` skill with:
```json
{"agent":"<agent>","feature":"<FEATURE>","conversation":<N>,"result":"<RESULT>","total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>,"wall_seconds":<computed>}
```
(`wall_seconds` is the fallback computed from `<STAGE>_START`; `log-agent-done` prefers
`duration_ms` if > 0.)

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
