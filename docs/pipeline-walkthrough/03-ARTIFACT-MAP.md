# 03 — Artifact Map: security-fixes

Every file produced or consumed during this pipeline run.
Files are listed by their role in the pipeline, not alphabetically.

---

## Plan files (the FSM's persistent state)

These 4 files are the "lite rigor" plan. Together they are the pipeline's
memory — an interrupted run can be resumed by reading PROGRESS.md and
re-entering at the last incomplete conversation.

### [plans/security-fixes/USER_STORIES.md](../security-fixes/USER_STORIES.md)
**Written by:** Planner  
**Read by:** Tester (acceptance criteria source)  
**Updated by:** Builder (Story 3b wording fix — user decision)

Contains 6 user stories with acceptance criteria. Each story maps to one fix.
Stories use the "As / I want / So that / Acceptance criteria / Delivered by"
structure. The tester checks every acceptance criterion line-by-line against
running code and test output.

Stories delivered by Conversation 1 (code): 1, 2, 3a, 3b, 4  
Stories delivered by Conversation 2 (docs/config): 5, 6

---

### [plans/security-fixes/IMPLEMENTATION_PLAN.md](../security-fixes/IMPLEMENTATION_PLAN.md)
**Written by:** Planner  
**Read by:** Planner (when writing CONVERSATION_PROMPTS.md)

Contains the exact code changes — file paths, before/after snippets, insertion
points. This is the "how" document. Deliberately more detailed than the
conversation prompts need to be, so the conversation prompts can be concise.

---

### [plans/security-fixes/CONVERSATION_PROMPTS.md](../security-fixes/CONVERSATION_PROMPTS.md)
**Written by:** Planner  
**Read by:** Builder agents (primary instruction source)

Contains the verbatim prompts given to each builder. These are self-contained —
a builder reading only this file has everything needed to implement its conversation.
Includes exact code snippets, file paths, and a scope boundary ("do not write tests").

Two conversations:
- Conversation 1: 4 code fixes (setup_command.py, materialize.py, server.py)
- Conversation 2: 2 docs/config fixes (.gitignore, SECURITY.md)

---

### [plans/security-fixes/PROGRESS.md](../security-fixes/PROGRESS.md)
**Written by:** Orchestrator  
**Read by:** Orchestrator (pipeline recovery), any resume command

Tracks which conversations are TODO vs DONE. The orchestrator updates this after
each conversation completes. If the pipeline is interrupted, reading PROGRESS.md
tells the orchestrator exactly where to resume.

```
| 1 | Code fixes      | 1, 2, 3a, 3b, 4 | DONE |
| 2 | Docs/config fixes | 5, 6           | DONE |
```

---

### [plans/security-fixes/RETRO.md](../security-fixes/RETRO.md)
**Written by:** Retro agent (manually persisted)  
**Read by:** Humans — before the next pipeline run, and by /lessons

A human-readable retrospective. NOT a technical log. Purpose: the team reads it
before starting the next feature to avoid repeating the same mistakes. It feeds
into `/lessons` which extracts repeating patterns and writes them to LESSONS.md.

Contains:
- What went well (keep doing)
- What required correction (surprised us)
- What to do differently next time (concrete changes to planning process)

---

## Lessons and patterns

### [LESSONS.md](../../LESSONS.md)
**Written by:** /lessons skill  
**Read by:** Planner (before every new plan)

Contains patterns extracted from one or more retros. A pattern is promoted to a
lesson only when it appears in 2+ features. The 4 entries from security-fixes
are currently single-source candidates — they become full lessons when confirmed
by a second feature.

Candidates from security-fixes:
- CANDIDATE-001: Docs stories over-specify format
- CANDIDATE-002: Redundant acceptance criteria confuse the tester
- CANDIDATE-003: Security features need explicit failure-case criteria
- CANDIDATE-004: Pre-existing broken tests should be flagged at pipeline start

---

## Transient feedback files (deleted after resolution)

These files no longer exist — they were the inter-agent communication medium and
were deleted once resolved. They are documented here as part of the record.

| File | Written by | Resolved by | Content |
|---|---|---|---|
| `plans/security-fixes/feedback/CONSULT_architect.md` | Architect (meet) | Builder Conv 1 (deleted) | Two pre-build gaps: single-pass uninstall risk, negative Content-Length bypass |
| `plans/security-fixes/feedback/REVIEW_FAILURES.md` (cycle 1) | Reviewer Conv 2 | Builder fix 1 (deleted when writing new version) | "server loop continues" contradicts server.py break behavior |
| `plans/security-fixes/feedback/REVIEW_FAILURES.md` (cycle 2) | Reviewer Conv 2 | Builder fix 2 (deleted) | "dropped and exits cleanly" still contradictory |
| `plans/security-fixes/feedback/TEST_FAILURES.md` | Tester run 1 | Builder story-update (deleted) | Story 3b criterion "server continues" — not satisfied |

---

## Source files changed

These are the deliverables — the actual fixes committed to the repo.

| File | Stories | What changed |
|---|---|---|
| `src/install_cli/setup_command.py` | 1, 4 | `ALLOWED_HOSTS` constant + validation loop in `main()`; `timeout=60` in `_uninstall_package()` |
| `src/install_cli/materialize.py` | 2 | Two-pass path-traversal guard in `uninstall()` — validates all entries before deleting any |
| `src/pathly_telemetry/server.py` | 3a, 3b | `_MAX_BODY` constant; `try/except ValueError` + negative-length check in `_read_message()` |
| `.gitignore` | 5 | Appended `.env`, `.env.*`, `*.env` patterns |
| `docs/SECURITY.md` | 6 | Two new sections: `## CLI Host Allowlist Bypass` and `## Telemetry Server DoS via Content-Length` |
| `tests/test_setup.py` | (pre-existing fix) | Replaced `test_no_flags_prints_no_writes_message` with `test_no_flags_launches_interactive_menu` — patches `_interactive_menu` to avoid stdin read under pytest |

---

## How pathly plan files relate to each other

```
USER_STORIES.md          ←── what to build (requirements)
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it (design)
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact prompts to builders (execution)
       │
       ▼
PROGRESS.md              ←── which conversations are done (state)
       │
       ▼
RETRO.md                 ←── what we learned (feedback loop to next feature)
       │
       ▼
LESSONS.md (root)        ←── promoted patterns (feedback loop to planner)
```

Each file is written by a different agent and read by the next agent in the chain.
No agent writes to the same file as the previous agent in normal flow — the pipeline
is strictly append-forward. Feedback loops (reviewer → builder → reviewer) are the
only exception, and they operate on the source files directly, not the plan files.
