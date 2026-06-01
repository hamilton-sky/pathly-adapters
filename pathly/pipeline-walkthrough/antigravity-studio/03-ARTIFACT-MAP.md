# 03 — Artifact Map: antigravity-studio

_Date: 2026-06-01 | Branch: master | Rigor: lite_

Who writes what, and what reads it.

---

## Plan artifacts

| Artifact | Written by | Read by | Purpose |
|---|---|---|---|
| `IMPLEMENTATION_PLAN.md` | planner | builder, orchestrator | Phase breakdown, file targets, done conditions |
| `USER_STORIES.md` | planner | builder, tester, reviewer | Acceptance criteria (S1.1, S2.1, S3.1, S3.2) |
| `CONVERSATION_PROMPTS.md` | planner | builder (each conv) | Exact prompts per conversation |
| `FEATURE_INDEX.md` | planner | builder, reviewer | File paths by phase |
| `PROGRESS.md` | orchestrator | team skill, help menu | Conv / story status tracking |
| `STATE.json` | orchestrator | FSM server | Current FSM state + conv number |
| `EVENTS.jsonl` | orchestrator + skills | retro, token usage | Append-only audit log |

---

## Build artifacts

| Artifact | Written by | Read by | Purpose |
|---|---|---|---|
| `VERIFY.md` | builder (manually) | FSM verify_gate | Typecheck result before REVIEWING |
| `feedback/REVIEW_FAILURES.md` | reviewer | builder | Violations to fix (deleted after resolution) |
| `REVIEW.md` | orchestrator | FSM require_artifact gate | Review summary / skip note |
| `RETRO.md` | quick agent | lessons, pipeline-walkthrough | Retrospective |

---

## Pipeline walkthrough artifacts

| Artifact | Written by | Purpose |
|---|---|---|
| `01-PIPELINE-FLOW.md` | quick agent | Execution trace — agent spawns, gates, feedback loops |
| `02-TOKEN-USAGE.md` | quick agent | Per-agent token and cost breakdown |
| `03-ARTIFACT-MAP.md` | quick agent | Who writes what |

---

## Source files changed

| File | Conv | Change |
|---|---|---|
| `studio/src/main/ipc/terminal.ts` | 1 | `'agy'` added to ALLOWED_SHELLS + resolveShell() (Win + non-Win) |
| `studio/src/renderer/src/types/terminal.ts` | 2 | `kind?` union extended with `'antigravity'` |
| `studio/src/renderer/src/store/chatStore.ts` | 2 | TerminalKind union, outputByTarget, clearOutputLines |
| `studio/src/renderer/src/lib/launchTerminal.ts` | 2 | `'agy'` → `'antigravity'` kind mapping; spawn branch |
| `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` (→ `useHQ.tsx`) | 2 + fix1 | Exhaustiveness cascade fixes; RF1–RF4 functional bugs fixed |
| `studio/src/renderer/src/components/ChatPanel/ChatInput/ChatInput.tsx` | 2 | prop types updated for new kind |
| `studio/src/renderer/src/components/Terminal/BrandIcons.tsx` | 3 | `AntigravityIcon` added (Google G, #1967D2) |
| `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` | 3 + fix1 | Antigravity button added; all buttons got `type="button"` |
| `studio/src/renderer/src/lib/studioSchema.ts` | 3 | `topbar-antigravity` schema item |
| `studio/src/renderer/src/components/HQ/useHQ.tsx` | fix1 + fix2 | RF1–RF4 all fixed; handleClearAll reset added |
| `studio/src/renderer/src/components/HQ/index.tsx` | fix1 | `renderTerminalCard('antigravity')` call added |
| `studio/src/renderer/src/components/HQ/MiniTerminalCard/MiniTerminalCard.tsx` | fix1 | `'antigravity'` target + `AntigravityIcon` |
| `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` | fix1 | `AntigravityIcon` imported; Antigravity flat button in action group |
| `studio/src/renderer/src/components/Terminal/Terminal.module.css` | fix1 | `.iconBtnAntigravity` + hover rule |

**Total files changed: 14**

---

## Commit map

| Commit | Contents |
|---|---|
| `16339ec` | Conv 1 — terminal.ts PTY wiring |
| `d6c3739` | Conv 2 — TerminalKind, chatStore, launchTerminal, useChatPanel/ChatInput |
| `c3ecd4d` | Conv 3 — BrandIcons, TerminalLauncher, studioSchema |
| `c5abe0a` | Fix cycle 1 — useHQ, PaneTabBar, MiniTerminalCard, HQ/index, TerminalLauncher type= |
| `c0e1788` | Fix cycle 2 — handleClearAll micro-fix |
