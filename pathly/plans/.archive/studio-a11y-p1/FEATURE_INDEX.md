---
name: Feature Index
---
# Studio A11y Phase 1 — Feature Index

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

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | `useFocusTrap` hook design + ARIA pattern decisions |
| `EDGE_CASES.md` | yes | readOnly chips, ContextMenu boundary, double-escape |
| `HAPPY_FLOW.md` | yes | Keyboard-only golden path through the app |
| `FLOW_DIAGRAM.md` | yes | Focus flow through modal and menu |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Conv 1 | Chip `<div>` → `<button type="button" role="switch" aria-checked>` |
| `studio/src/renderer/src/components/Editor/ConfigForm.module.css` | Conv 1 | Reset browser button defaults on `.chip` selector |
| `studio/src/renderer/src/components/NewItemDialog.tsx` | Conv 1 + Conv 2 | Conv 1: chip `<div>` → `<button>`; Conv 2: card gets `role="dialog"` + `aria-labelledby` |
| `studio/src/renderer/src/components/NewItemDialog.module.css` | Conv 1 | Reset browser button defaults on `.chip` selector |
| `studio/src/renderer/src/hooks/useFocusTrap.ts` | Conv 2 | CREATE — trap/restore focus within a dialog container |
| `studio/src/renderer/src/components/sidebar/shared/DeleteConfirmModal.tsx` | Conv 2 | Add `role="dialog"`, `aria-modal`, `aria-labelledby`, Escape handler, focus trap |
| `studio/src/renderer/src/components/ui/ContextMenu.tsx` | Conv 3 | Add `role="menu"`, `role="menuitem"`, arrow-key navigation |
| `studio/src/renderer/src/styles/tokens.css` | Conv 3 | Add `--text-disabled` variable in every theme block |
| `studio/src/renderer/src/styles/buttons.css` | Conv 3 | Replace `opacity: 0.35` on `:disabled` with `color: var(--text-disabled)` |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Chip toggles → semantic buttons | S1.1 | TODO | `ConfigForm.tsx`, `ConfigForm.module.css`, `NewItemDialog.tsx`, `NewItemDialog.module.css` |
| 2 | Modal ARIA + focus trap | S2.1 | TODO | `useFocusTrap.ts` (new), `DeleteConfirmModal.tsx`, `NewItemDialog.tsx` |
| 3 | ContextMenu ARIA + disabled tokens | S3.1, S4.1 | TODO | `ContextMenu.tsx`, `tokens.css`, `buttons.css` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/studio-a11y-p1/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
