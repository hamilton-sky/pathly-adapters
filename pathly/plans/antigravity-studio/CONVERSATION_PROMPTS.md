---
name: Conversation Guide
---
# antigravity-studio — Conversation Guide

Split into 3 conversations. Each produces type-checked, runnable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Main-process PTY wiring (Phases 0–1)

**Stories delivered:** S1.1

**Prompt to paste:**
```
Read pathly/plans/antigravity-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-studio Conversation 1 (Phases 0–1) from pathly/plans/antigravity-studio/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read to confirm every path below exists.

**Codebase files this conversation touches:**
- `studio/src/main/ipc/terminal.ts` — MODIFY (ALLOWED_SHELLS + resolveShell)

**Phase 0 — Pre-flight:**
- Read `studio/src/main/ipc/terminal.ts` in full. Note:
  - The exact line where ALLOWED_SHELLS is defined and its current contents
  - The exact shape of resolveShell() — how it handles 'claude' and 'codex'
- Run `cd studio && npm run typecheck 2>&1 | tail -10` and record any pre-existing errors as baseline.

**Phase 1 — ALLOWED_SHELLS + resolveShell:**
- Add `'agy'` to the ALLOWED_SHELLS array.
- In resolveShell(), add an `'agy'` case that mirrors the `'codex'` case exactly — only change the command string from `'codex'` to `'agy'`.
  - Windows: powershell.exe -NoExit -Command agy
  - non-Windows: bash -c exec agy
- Do NOT touch any other code in terminal.ts or any other file.

Architectural rules to observe:
- Main process only — do NOT touch any renderer files.
- No new IPC channels — the existing terminal:spawn channel is sufficient.

Verify: `cd studio && npm run typecheck`
After done, update pathly/plans/antigravity-studio/PROGRESS.md Conv 1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `terminal.ts` has `'agy'` in allowlist and resolveShell; typecheck passes.
**Files touched:** `studio/src/main/ipc/terminal.ts`

---

## Conversation 2: Renderer types and logic (Phase 2)

**Stories delivered:** S2.1

**Prompt to paste:**
```
Read pathly/plans/antigravity-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-studio Conversation 2 (Phase 2) from pathly/plans/antigravity-studio/IMPLEMENTATION_PLAN.md.

**Before editing anything:**
- Read `studio/src/renderer/src/types/terminal.ts` in full — note the exact TerminalKind definition.
- Read `studio/src/renderer/src/store/chatStore.ts` — check if it imports TerminalKind from types/terminal.ts or re-declares it.
- Read `studio/src/renderer/src/lib/launchTerminal.ts` in full — note the kind determination chain and prompt patterns object.
- Check PROGRESS.md — Conv 1 must be DONE.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/types/terminal.ts` — MODIFY
- `studio/src/renderer/src/store/chatStore.ts` — MODIFY (only if it re-declares TerminalKind)
- `studio/src/renderer/src/lib/launchTerminal.ts` — MODIFY

**Phase 2:**

`types/terminal.ts`: Add `'antigravity'` to the TerminalKind union.

`chatStore.ts`: Only edit if it has its own TerminalKind union (not an import). If it imports from types/terminal.ts, skip this file.

`launchTerminal.ts`:
1. Kind determination — add `command === 'agy' ? 'antigravity' :` before the 'shell' fallback.
2. Prompt patterns — add `antigravity: ['> ']` (same as claude/codex).
3. Any exhaustive switch or if-else on TerminalKind — add the 'antigravity' branch (mirror the 'codex' branch).

Do NOT touch TerminalLauncher.tsx, BrandIcons.tsx, or studioSchema.ts — those are Conversation 3.

Architectural rules to observe:
- Renderer only — do NOT touch main process files.
- TypeScript unions must be exhaustive — if TypeScript reports a missing branch after your edit, fix it.

Verify: `cd studio && npm run typecheck`
After done, update pathly/plans/antigravity-studio/PROGRESS.md Conv 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `TerminalKind` includes `'antigravity'`; `launchTerminal('agy')` maps to `'antigravity'`; typecheck passes.
**Files touched:** `types/terminal.ts`, `chatStore.ts` (if applicable), `launchTerminal.ts`

---

## Conversation 3: UI components and schema (Phase 3)

**Stories delivered:** S3.1, S3.2

**Prompt to paste:**
```
Read pathly/plans/antigravity-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-studio Conversation 3 (Phase 3) from pathly/plans/antigravity-studio/IMPLEMENTATION_PLAN.md.

**Before editing anything:**
- Read `studio/src/renderer/src/components/Terminal/BrandIcons.tsx` in full — understand the icon component pattern (inline SVG? size prop? how are ClaudeIcon and CodexIcon structured?).
- Read `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` in full — understand how options are rendered (button per kind? dropdown items? what props does each need?).
- Read `studio/src/renderer/src/lib/studioSchema.ts` lines 50–80 — understand the topbar item schema shape.
- Check PROGRESS.md — Conv 2 must be DONE.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/Terminal/BrandIcons.tsx` — MODIFY
- `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` — MODIFY
- `studio/src/renderer/src/lib/studioSchema.ts` — MODIFY

**Phase 3:**

`BrandIcons.tsx` (do this first):
Add AntigravityIcon following the exact same pattern as ClaudeIcon or CodexIcon.
The icon is a Google G lettermark SVG, fill color #1967D2 (Antigravity blue).
Use the SVG path from IMPLEMENTATION_PLAN.md Phase 3 details.
Export it the same way the other icons are exported.

`TerminalLauncher.tsx`:
Import AntigravityIcon from BrandIcons.tsx.
Add an Antigravity option following the same pattern as the Codex option.
Label: "Antigravity" (or "agy" — match whatever label style the other options use).
On click: call launchTerminal (or equivalent) with command = 'agy'.

`studioSchema.ts`:
Add a 'topbar-antigravity' item following the same shape as 'topbar-codex' (line ~69).
Use label 'Antigravity', command 'agy', and whatever icon field the schema uses.

Architectural rules to observe:
- Follow the no-inline-styles rule from studio/CLAUDE.md — use CSS modules or existing style tokens.
- Component size limit from studio/CLAUDE.md — keep the icon component under the stated line limit.
- Do NOT modify core layout files outside the three listed files.

Verify: `cd studio && npm run typecheck`
After the verify command passes, write pathly/plans/antigravity-studio/VERIFY.md with first line `RESULT: PASS` and a one-line summary.
After done, update pathly/plans/antigravity-studio/PROGRESS.md Conv 3 to DONE and Status to COMPLETE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Antigravity button renders in topbar dropdown with Google G icon; typecheck passes; VERIFY.md written.
**Files touched:** `BrandIcons.tsx`, `TerminalLauncher.tsx`, `studioSchema.ts`
