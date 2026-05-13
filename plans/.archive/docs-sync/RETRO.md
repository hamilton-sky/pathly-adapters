# docs-sync — Retrospective

_Date: 2026-05-11 | Rigor: lite | Conversations: 1_

---

## Plan Quality

**Conversation sizing:** Too big — the single conversation covered 5 stories across 3+ files. The builder acted on the audit's findings without re-verifying the real codebase layout first. This caused two full review cycles (builder fixed the wrong paths because the plan baked in stale facts rather than instructing the builder to re-derive them from the live repo).

**Surprises:** None beyond the scope drift. No architectural violations, integration failures, or test failures that weren't caused by the stale-fact issue.

**Missing from plan:**
1. **Criticality assessment** — the plan didn't evaluate how critical or structurally central the files being changed were. A docs file that references entry points is high-criticality (incorrect entry points mislead any reader trying to set up the project). That should change the verification bar.
2. **Task-to-progress alignment** — the implementation plan template has phases/fixes listed as prose, but PROGRESS.md tracks at the conversation level. There's no task-level checkbox bridge between the two. The planner filled in PROGRESS.md tasks manually; the template should enforce that each IMPLEMENTATION_PLAN phase maps to exactly one PROGRESS.md row.
3. **Feature folder index / agent router** — agents had to glob and read multiple plan files to orient themselves. A single `FEATURE_INDEX.md` (or `AGENT_ROUTER.md`) listing every file in the feature folder with a one-line description of its role would let each agent load context in one read instead of several. This is especially valuable when the builder is handed a conversation prompt without knowing which plan files exist.

---

## What Worked

- Lite rigor was right for this scope — 4 plan files, one conversation, no architecture complexity.
- The reviewer caught real structural errors (invented package names, wrong entry points) that the builder missed.
- The escalation mechanism (HUMAN_QUESTIONS.md) surfaced the retry-limit issue cleanly; the direct fix was faster than another agent cycle.
- Acceptance criteria as grep commands (S1–S5) made the tester pass/fail deterministic — no ambiguity.

---

## What to Improve Next Time

- **Builder MUST re-verify live paths before editing** — never trust audit findings baked into the plan prompt as final truth. The plan prompt should explicitly say: "Glob these paths first and correct any discrepancy before editing."
- **Implementation plan phases should map 1:1 to PROGRESS.md rows** — planner should produce a phase per PROGRESS row, not a flat list of fixes.
- **Add a FEATURE_INDEX.md template** — one file per feature folder that lists all plan files and their role. Agents load this first, then fetch only what they need.
- **Criticality flag in USER_STORIES.md** — each story should carry a `criticality: low/medium/high` tag. High-criticality stories (entry points, public paths, schema) get extra verification steps in CONVERSATION_PROMPTS.md.

---

## Seed for Next Storm

> docs-sync revealed that builder agents act on plan-baked facts instead of re-verifying the live codebase. The key fix is a "verify before edit" step in every conversation prompt for docs/config changes. It also exposed a missing feature-folder index: agents currently have to discover plan files by globbing, which wastes context and causes orientation errors. A lightweight FEATURE_INDEX.md would solve this.
