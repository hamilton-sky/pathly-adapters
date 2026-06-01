# Retrospective — antigravity-studio

_Date: 2026-06-01 | Rigor: lite | Conversations: 3_

---

## What went well

- **All 4 stories delivered in 3 conversations.** PTY wiring (S1.1), renderer kind system (S2.1), topbar button (S3.1), and brand icon (S3.2) all shipped and pass all 10 acceptance criteria.
- **Reviewer caught real functional bugs.** The Conv 2 exhaustiveness fixes in `useHQ.tsx` left `terminalBuffers`, `idleTimers`, the PTY subscription loop, and `renderTerminalCard` all missing the `'antigravity'` case — these would have silently broken Antigravity PTY output capture and HQ header chips at runtime. The reviewer found all of them in the first pass.
- **Designer scan found a missing touchpoint.** `PaneTabBar.tsx` had a three-button action group (Shell, Claude, Codex) that was never in the plan. The designer's read of the live component tree caught it, and the builder added Antigravity there in the same fix cycle.
- **TypeScript as a safety net.** The exhaustiveness cascade in Conv 2 (useChatPanel.tsx → ChatInput.tsx) forced correct wiring of the new kind through all type-checked surfaces — a runtime bug would have been silent, but TypeScript made it impossible to miss.

---

## What was harder than expected

- **`useChatPanel.tsx` was renamed to `useHQ.tsx`.** The plan's file paths were stale. The builder had to glob for the correct file, adding orientation overhead that could have been a plan verification step.
- **Conv 2 exhaustiveness scope underestimated.** The plan said "add `'antigravity'` to the TerminalKind union in 3 files." The actual impact cascaded to 5 files (`types/terminal.ts`, `chatStore.ts`, `launchTerminal.ts`, `useChatPanel.tsx`, `ChatInput.tsx`) plus partial fixes that left the PTY buffer/subscription/cleanup wiring incomplete — requiring a full reviewer fix cycle.
- **Two reviewer passes needed.** First pass found 6 violations; second pass found 1 more (`handleClearAll` missing `setCommandRunning('antigravity', false)`). Total: 3 builder runs for Conv 3 (initial + two fix cycles).
- **verify_gate fired at Conv 1** before VERIFY.md existed. Required manual file creation and conv_start_sha update — same friction as antigravity-adapter.

---

## What to do differently next time

1. **Include exhaustiveness audit in Conv N completion criteria.** When adding a new TerminalKind value, Conv N's done-condition must include: "grep `useChatPanel\|useHQ` for all arrays and switch statements on TerminalKind and confirm `'antigravity'` appears in each." One grep in the prompt = two reviewer fix cycles saved.
2. **Add `PaneTabBar.tsx` to S3.1 acceptance criteria.** The plan said "Antigravity option in topbar terminal launcher dropdown" but the terminal panel tab strip has its own launcher. Any story about adding a CLI option needs to cover both launch surfaces.
3. **Verify file paths in FEATURE_INDEX.md at planning time.** `useChatPanel.tsx` → `useHQ.tsx` rename was not reflected in the plan. Add a "path verification" step to planning: glob each codebase path in FEATURE_INDEX.md before finalizing the plan.

---

## Metrics

| Metric | Value |
|---|---|
| Conversations | 3 |
| Agents spawned | builder ×5, reviewer ×2, tester ×1 |
| Reviewer passes | 2 (found violations both times) |
| Gate failures | 1 (verify_gate at Conv 1) |
| Acceptance criteria | 10/10 PASS |
| TypeScript: before | 0 errors |
| TypeScript: after | 0 errors |
| Files touched | 11 |
| Total cost (captured) | ~$1.37 |
