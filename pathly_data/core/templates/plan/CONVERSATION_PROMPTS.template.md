# [Feature Name] — Conversation Guide

Split into N conversations (max 4). Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: [Title] (Phases X-Y)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Implement [Feature] Conversation 1 (Phases X-Y) from plans/$ARGUMENTS/IMPLEMENTATION_PLAN.md.

Scope:
- Phase X: [specific instructions with file paths and layer]
- Phase Y: [specific instructions with file paths and layer]

Architectural rules to observe:
- [Read CLAUDE.md and .claude/rules/ for project-specific rules before implementing]
- Stay within the stated layer. Do not touch other layers.

Do NOT touch [exclusions — other layers, other sites, exam tests, etc.].
Verify: <project verify command>
After done, update plans/$ARGUMENTS/PROGRESS.md phases X-Y to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** [what state the codebase should be in — which actions are registered and runnable]
**Files touched:** `[file list]`

---

## Conversation 2: [Title] (Phases X-Y)
...
