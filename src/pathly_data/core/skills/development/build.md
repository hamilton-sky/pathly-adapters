# build

This is the canonical, tool-agnostic Pathly behavior for the build workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Parse `$ARGUMENTS`: the first word is the **plan folder name** (FEATURE), and if a second word "auto" is present, that signals non-interactive auto-flow mode. For example, `continue refactor-main auto` -> plan = `refactor-main`, auto mode = true.

## Feature detection

If the first word of `$ARGUMENTS` is a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `plans/` folder exists or is empty: stop →
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

For non-trivial conversations (touches multiple files or an unfamiliar area), run a three-phase build before Step 5:

**Phase 1 — Analyze:**
Spawn `builder` with `phase: analyze` prepended to the conversation prompt:
```
phase: analyze
[conversation prompt]
```
Parse the `## NEEDS_CONTEXT` block it returns. If the block says `none`: skip Phase 2.

**Phase 2 — Scout (if NEEDS_CONTEXT has entries):**
Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: builder` + the question
- `type: scout` → spawn `scout` with `ROLE: builder` + scope + question

Use the returned compressed summary as Scout Findings.

**Phase 3 — Implement (Step 5):**
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

Find the plan folder at `plans/$PLAN/`. If it doesn't exist, list all `plans/*/` folders and ask which one the user meant.

## Step 3: Read current state

Read these files:

1. **`plans/$PLAN/PROGRESS.md`** — Find the first row in the "Conversation Breakdown" table with status **TODO**. That is the next target conversation. Also check overall Status — if COMPLETE, stop and report.

2. **`plans/$PLAN/CONVERSATION_PROMPTS.md`** — Find the section for the target conversation number. Extract:
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

## Step 7: Report completion

After successful verification, report:

```
## Completed: Conv N — [title]
- Files modified: [list]
- Verification: passed
```

Do NOT update PROGRESS.md. Do NOT commit. The orchestrator (`/pathly team`) handles both after the reviewer passes.

## Exit contract

Write `plans/<feature>/STATE.json`:
```json
{"current": "REVIEWING", "feature": "<feature>", "rigor": "<rigor>", "updated_at": "<iso-timestamp>"}
```

After the builder agent completes (Phase 3 — Implement), parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Compute wall_seconds: run `python -c "import time; print(int(time.time()) - BUILD_START)"` using `BUILD_START` from Step 4.5 (used as fallback if duration_ms is 0).

Append to `plans/<feature>/EVENTS.jsonl`:
```
{"type": "AGENT_DONE", "agent": "builder", "model": "<model>", "conversation": <N>, "result": "DONE", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "tool_uses": <tool_uses>, "wall_seconds": <computed>, "ts": "<iso-timestamp>"}
{"type": "STATE_TRANSITION", "to": "REVIEWING", "ts": "<iso-timestamp>"}
```

Note: tokens/cost are 0 in the Claude Code path; runner.py populates them automatically when running via `pathly-run` CLI.

Then invoke the `record-cost` skill with:
```json
{"agent":"builder","feature":"<feature>","summary":"Conv <N> build complete","conversation":<N>,"wall_seconds":<computed>,"total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>}
```

Do not invoke any other skill. The orchestrator reads STATE.json and decides what comes next.

## Edge Cases

- **All conversations DONE**: Report "Plan $PLAN is already COMPLETE."
- **No CONVERSATION_PROMPTS.md**: Fall back to reading IMPLEMENTATION_PLAN.md directly for the next TODO phase.
- **Blocked conversation**: Report the blocker and stop.
