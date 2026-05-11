# 01 — Pipeline Flow: security-fixes

This documents every agent spawn, every feedback loop, and every gate in the
security-fixes run. Read top to bottom — it is in execution order.

---

## Pipeline map

```
User: "is my project secure?"
│
│  [Stage 0 — Discovery]
├─► Explore agent         reads entire src/ tree
├─► Reviewer agent        security audit → 6 vulnerabilities found
│   └─ User: "fix all — use pathly team-flow"
│
│  [Stage 1 — Plan]  (user skipped discovery, entered at plan)
├─► Planner agent         writes 4 plan files (lite rigor)
│   Produces:
│     plans/security-fixes/USER_STORIES.md
│     plans/security-fixes/IMPLEMENTATION_PLAN.md
│     plans/security-fixes/CONVERSATION_PROMPTS.md
│     plans/security-fixes/PROGRESS.md
│
│  [Stage 1b — Architect Consult]  (/pathly meet)
├─► Architect agent       reads plan files + src/ code
│   Flags two gaps the planner missed:
│     (1) single-pass uninstall allows partial deletion
│     (2) negative Content-Length bypasses naïve > _MAX_BODY check
│   Produces: plans/security-fixes/feedback/CONSULT_architect.md
│   User: "go"
│
│  [Stage 2 — Build: Conversation 1 — Code fixes]
├─► Builder agent (Conv 1)
│   Reads:  CONVERSATION_PROMPTS.md, CONSULT_architect.md, source files
│   Writes: src/install_cli/setup_command.py    (ALLOWED_HOSTS + timeout)
│           src/install_cli/materialize.py      (two-pass path-traversal guard)
│           src/pathly_telemetry/server.py      (_MAX_BODY cap + ValueError guard)
│   Deletes: CONSULT_architect.md
│
│  [Stage 3 — Review: Conversation 1]
├─► Reviewer agent (Conv 1)
│   Reads: git diff of all changed files
│   Result: PASS — all 4 fixes correct, two-pass uninstall confirmed
│   No feedback file written → pipeline advances
│
│  [Stage 2 — Build: Conversation 2 — Docs/config fixes]
├─► Builder agent (Conv 2)
│   Reads:  CONVERSATION_PROMPTS.md, .gitignore, docs/SECURITY.md
│   Writes: .gitignore               (.env / .env.* / *.env appended)
│           docs/SECURITY.md         (two new sections inserted)
│
│  [Stage 3 — Review: Conversation 2 — Cycle 1]
├─► Reviewer agent (Conv 2, pass 1)
│   FAIL: SECURITY.md line 146 says "server loop continues"
│         but server.py's run() breaks on None — contradiction
│   Produces: plans/security-fixes/feedback/REVIEW_FAILURES.md
│
│  [Stage 2 — Build: Fix cycle 1]
├─► Builder agent (fix 1)
│   Reads:  REVIEW_FAILURES.md, docs/SECURITY.md
│   Writes: docs/SECURITY.md  (changes "loop continues" → "server process exits cleanly")
│   Note: still contradictory — "dropped and exits" is ambiguous
│
│  [Stage 3 — Review: Conversation 2 — Cycle 2]
├─► Reviewer agent (Conv 2, pass 2)
│   FAIL: "dropped and the server process exits cleanly" still contradictory
│         "dropped" implies loop continues; "exits cleanly" says it terminates
│   Produces: plans/security-fixes/feedback/REVIEW_FAILURES.md
│
│  [Stage 2 — Build: Fix cycle 2]
├─► Builder agent (fix 2)
│   Reads:  REVIEW_FAILURES.md, docs/SECURITY.md
│   Writes: docs/SECURITY.md  (rewrites entire bullet — removes "dropped",
│           replaces with "causes _read_message() to return None, which
│           terminates the server process cleanly")
│   Deletes: REVIEW_FAILURES.md
│
│  [Stage 3 — Review: Conversation 2 — Cycle 3 / Final]
├─► Reviewer agent (Conv 2, pass 3)
│   PASS — wording now accurate and consistent
│   No feedback file written → pipeline advances
│
│  [Stage 4 — Test: Run 1]
├─► Tester agent (run 1)
│   Runs: pytest + acceptance criteria check against USER_STORIES.md
│   Result:
│     Stories 1, 2, 3a, 4, 5, 6 → PASS
│     Story 3b: NOT COVERED — "server continues handling subsequent messages"
│               is not satisfied (server terminates, not continues)
│   Produces: plans/security-fixes/feedback/TEST_FAILURES.md
│   Orchestrator explains design decision to user
│   User: "option 1" — accept terminate behavior, update the story
│
│  [Stage 2 — Build: Story update]
├─► Builder agent (story fix)
│   Reads:  TEST_FAILURES.md, USER_STORIES.md
│   Writes: USER_STORIES.md  (Story 3b criterion updated to "terminates cleanly")
│   Deletes: TEST_FAILURES.md
│
│  [Stage 4 — Test: Run 2]
├─► Tester agent (run 2)
│   All stories PASS
│   Flags additional issues (out of scope):
│     - Pre-existing broken test: test_no_flags_prints_no_writes_message
│     - Coverage gap: no unit tests for security behaviors themselves
│   User: "fix the pre-existing test and then go to retro"
│
│  [Stage 2 — Build: Test fix]
├─► Builder agent (test fix)
│   Reads:  tests/test_setup.py
│   Writes: tests/test_setup.py  (replaces broken test with mock-based version)
│   Result: 16/16 tests pass
│
│  [Stage 5 — Retro]
└─► Retro agent
    Reads:  all plan files, git diff
    Writes: plans/security-fixes/RETRO.md
    (file did not persist from agent; written manually from agent output)

[Post-pipeline]
    git commit → git push → /lessons → LESSONS.md written
```

---

## How agents communicate

Agents never call each other. The orchestrator (main assistant) is the only router.
Communication happens in two ways:

### 1. Plan files (sequential hand-off)
Each agent reads the plan files the previous stage wrote. The builder reads
CONVERSATION_PROMPTS.md to know exactly what to implement. The reviewer reads
git diff. The tester reads USER_STORIES.md for acceptance criteria.

### 2. Feedback files (blocking gates)
A feedback file in `plans/<feature>/feedback/` means "blocked — action required."

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `CONSULT_architect.md` | Architect | Builder (deletes it) | Pre-build findings to incorporate |
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes it) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes it) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline cannot proceed without human decision |

The orchestrator checks `plans/<feature>/feedback/` before every forward advance.
If any file exists, it routes to the responsible agent instead of advancing.
Only when the folder is empty does the pipeline move to the next stage.

---

## FSM states traversed (security-fixes)

```
IDLE
  → PLANNING          (planner spawned)
  → PLAN_DONE         (4 files written)
  → CONSULT_OPEN      (/pathly meet — architect writes CONSULT_architect.md)
  → BUILDING_CONV_1   (builder spawned)
  → REVIEWING_CONV_1  (reviewer spawned)
  → BUILDING_CONV_2   (builder spawned)
  → REVIEW_BLOCKED    (REVIEW_FAILURES.md written — cycle 1)
  → BUILDING_CONV_2   (builder fix spawned)
  → REVIEW_BLOCKED    (REVIEW_FAILURES.md written — cycle 2)
  → BUILDING_CONV_2   (builder fix spawned)
  → REVIEWING_CONV_2  (reviewer spawned — cycle 3)
  → TESTING           (tester spawned — run 1)
  → TEST_BLOCKED      (TEST_FAILURES.md written)
  → BUILDING_STORY    (builder story-update spawned)
  → TESTING           (tester spawned — run 2)
  → TEST_PASS         (all stories satisfied)
  → RETRO             (retro agent spawned)
  → DONE
```

---

## Feedback loop summary

| Stage | Loops | Cause |
|---|---|---|
| Review Conv 2 | 2 loops | Ambiguous wording in SECURITY.md — took 3 reviewer passes |
| Test run 1 | 1 loop | Story 3b criterion did not match actual server behavior |
| Pre-existing test | 1 fix | test_no_flags_prints_no_writes_message crashed on stdin under pytest |

Max allowed loops per file per conversation: **2** (FSM guard). This run hit the limit
on review (cycle 2 of 2). A third failure would have escalated to HUMAN_QUESTIONS.md.
