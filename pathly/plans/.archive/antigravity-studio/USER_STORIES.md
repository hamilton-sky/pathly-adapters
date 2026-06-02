---
name: User Stories
---
# antigravity-studio — User Stories

## Context
The Pathly Studio Electron app has a terminal panel that can open interactive PTY sessions for three kinds: `shell` (native bash/PowerShell), `claude` (Claude Code CLI), and `codex` (OpenAI Codex CLI). Each kind has a dropdown button in the topbar, a brand icon on the tab, and a PTY spawner entry in the main process.

This feature adds Antigravity (`agy` CLI) as a fourth terminal kind — `antigravity` — so users can open an `agy` session directly from the studio alongside their other terminals.

---

## Stories

### Story S1.1: PTY spawn support for `agy`
**As a** developer using the studio, **I want** the main process to spawn an `agy` PTY session when I open an Antigravity terminal, **so that** the `agy` CLI runs in a proper interactive pseudo-terminal inside the studio.

**Acceptance Criteria:**
- [ ] `'agy'` appears in the `ALLOWED_SHELLS` allowlist in `studio/src/main/ipc/terminal.ts`
- [ ] `resolveShell()` handles `'agy'`: on Windows → `powershell.exe -NoExit -Command agy`; on non-Windows → `bash -c exec agy`
- [ ] Sending `terminal:spawn` IPC with `command = 'agy'` does not throw an "unsupported shell" error

**Edge Cases:**
- `agy` binary is not installed — PTY spawn fails; the terminal tab should show the shell error output rather than crashing the app
- On Windows, `powershell.exe` wrapping is required (same as `claude` and `codex`)

**Delivered by:** Phase 0–1 → Conversation 1

---

### Story S2.1: Renderer kind system recognises `antigravity`
**As a** developer using the studio, **I want** the renderer to treat `'antigravity'` as a valid terminal kind, **so that** `launchTerminal`, the chat store, and type-checked code all handle it without errors or type warnings.

**Acceptance Criteria:**
- [ ] `TerminalKind` in `studio/src/renderer/src/types/terminal.ts` includes `'antigravity'`
- [ ] `chatStore.ts` `TerminalKind` union includes `'antigravity'`
- [ ] `launchTerminal.ts` maps command `'agy'` to kind `'antigravity'`
- [ ] `launchTerminal.ts` includes a prompt pattern for `'antigravity'` (use `'> '` — same as claude/codex)
- [ ] `cd studio && npm run typecheck` exits 0 with no new errors

**Edge Cases:**
- Any exhaustive switch/if-else on `TerminalKind` must handle `'antigravity'` — TypeScript will catch missing branches at typecheck

**Delivered by:** Phase 2 → Conversation 2

---

### Story S3.1: Antigravity terminal button in topbar
**As a** developer using the studio, **I want** an Antigravity option in the topbar terminal launcher dropdown, **so that** I can open an `agy` session with one click.

**Acceptance Criteria:**
- [ ] `TerminalLauncher.tsx` renders an Antigravity option alongside Shell / Claude / Codex
- [ ] Clicking it calls `launchTerminal` with `command = 'agy'`
- [ ] `studioSchema.ts` includes a `'topbar-antigravity'` item

**Edge Cases:**
- Dropdown overflow on narrow screens — existing layout handles this; no special treatment needed

**Delivered by:** Phase 3 → Conversation 3

---

### Story S3.2: Antigravity brand icon on terminal tab
**As a** developer using the studio, **I want** the Antigravity terminal tab to show a Google G icon in Antigravity blue, **so that** I can distinguish it from Shell, Claude, and Codex tabs at a glance.

**Acceptance Criteria:**
- [ ] `BrandIcons.tsx` exports an `AntigravityIcon` component
- [ ] The icon renders a Google G shape (`G`) as an inline SVG, filled with Antigravity blue (`#1967D2` — verify from Antigravity brand page before finalising)
- [ ] The icon is used by `TerminalLauncher.tsx` and the tab bar for kind `'antigravity'`
- [ ] `cd studio && npm run typecheck` exits 0 after adding the icon

**Edge Cases:**
- If Antigravity's exact brand hex is not known at build time, use `#1967D2` (Google primary blue) with a TODO comment — do not block the story on brand confirmation

**Delivered by:** Phase 3 → Conversation 3
