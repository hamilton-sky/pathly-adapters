---

---


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

## Step 3: Read current state

Read these files:

1. **`pathly/features/$PLAN/PROGRESS.md`** — Find the first row in the "Conversation Breakdown" table with status **TODO**. That is the next target conversation. Also check overall Status — if COMPLETE, stop and report.

2. **`pathly/features/$PLAN/CONVERSATION_PROMPTS.md`** — Find the section for the target conversation number. Extract:
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

## Step 4.6: Board task DAG (preferred work source)

If this feature has a board task DAG, it is the **authoritative** work list — drain it
**instead of** the conversation prompt (the DAG supersedes `CONVERSATION_PROMPTS.md`):

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
3. **If the list is empty or the endpoint is unreachable**, fall through to Step 5 and build
   the conversation prompt read in Step 3 — the legacy path, unchanged. Features with no board
   DAG (older plans) work exactly as before.

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

- **All conversations DONE**: Report "Plan $PLAN is already COMPLETE."
- **No CONVERSATION_PROMPTS.md**: Fall back to reading IMPLEMENTATION_PLAN.md directly for the next TODO phase.
- **Blocked conversation**: Report the blocker and stop.
