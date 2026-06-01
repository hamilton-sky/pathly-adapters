---
name: Feature Index
---
# antigravity-studio — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | IPC pattern, kind system, icon approach |
| `EDGE_CASES.md` | yes | TypeScript union exhaustiveness, Windows path, missing binary |
| `HAPPY_FLOW.md` | yes | User opens Antigravity tab, types command, gets response |
| `FLOW_DIAGRAM.md` | yes | Data flow: UI button → IPC → PTY → agy process |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/main/ipc/terminal.ts` | Conv 1 | Add `'agy'` to `ALLOWED_SHELLS`; add `'agy'` case to `resolveShell()` |
| `studio/src/renderer/src/types/terminal.ts` | Conv 2 | Add `'antigravity'` to `TerminalKind` type union |
| `studio/src/renderer/src/store/chatStore.ts` | Conv 2 | Add `'antigravity'` to `TerminalKind` union in store |
| `studio/src/renderer/src/lib/launchTerminal.ts` | Conv 2 | Add `agy → antigravity` kind branch; add prompt pattern |
| `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` | Conv 3 | Add Antigravity option to dropdown |
| `studio/src/renderer/src/components/Terminal/BrandIcons.tsx` | Conv 3 | Add `AntigravityIcon` — Google G SVG in Antigravity blue |
| `studio/src/renderer/src/lib/studioSchema.ts` | Conv 3 | Add `'topbar-antigravity'` schema item |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Main-process PTY wiring | S1.1 | TODO | `terminal.ts` |
| 2 | Renderer types and logic | S2.1 | TODO | `types/terminal.ts`, `chatStore.ts`, `launchTerminal.ts` |
| 3 | UI components and schema | S3.1, S3.2 | TODO | `TerminalLauncher.tsx`, `BrandIcons.tsx`, `studioSchema.ts` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/antigravity-studio/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
