---
name: Implementation Plan
---
# antigravity-studio — Implementation Plan

## Overview
Adds Antigravity (`agy` CLI) as a fourth terminal kind in the Pathly Studio Electron app. The existing `shell` / `claude` / `codex` kind system is extended in 7 files across two layers: main process (PTY spawn allowlist and shell resolver) and renderer (type union, store, launch logic, topbar button, brand icon, schema). No new IPC channels are needed — the existing `terminal:spawn` channel accepts any allowed shell command.

## Layer Architecture

```
User clicks "Antigravity" in TerminalLauncher.tsx (renderer)
  → launchTerminal('agy') determines kind = 'antigravity'
  → window.pathly.terminal.spawn(tabId, projectPath, 'agy')  [IPC via preload]
  → ipcMain.handle('terminal:spawn') in terminal.ts
  → ALLOWED_SHELLS check: 'agy' ✓
  → resolveShell('agy') → ['powershell.exe', '-NoExit', '-Command', 'agy']  (Windows)
  → pty.spawn(shell, args, { cwd, env })
  → PTY output streamed back via 'terminal:data' IPC → xterm display
```

---

## Prerequisites
- `studio/src/main/ipc/terminal.ts` exists — verified by glob
- `studio/src/renderer/src/types/terminal.ts` exists — verified by glob
- `cd studio && npm run typecheck` exits 0 at baseline (record any pre-existing errors)

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** *(no file written)*
**Done when:** Builder has read `studio/src/main/ipc/terminal.ts` (full file), confirmed the exact `ALLOWED_SHELLS` array and `resolveShell()` function shape, and recorded baseline typecheck result.
**Depends on:** nothing
**Enables:** Phase 1 — must know exact code shape before editing
**Details:**
- Read `studio/src/main/ipc/terminal.ts` in full. Note the exact line numbers for `ALLOWED_SHELLS` and `resolveShell()`.
- Read `studio/src/renderer/src/types/terminal.ts` in full. Note the exact `TerminalKind` definition.
- Run `cd studio && npm run typecheck 2>&1 | tail -5` and record any pre-existing errors as baseline.
**Verify:** *(pre-flight only — no new code)*

---

### Phase 1: ALLOWED_SHELLS + resolveShell   ← Conversation: 1
**File:** `studio/src/main/ipc/terminal.ts` — MODIFY
**Done when:** `ALLOWED_SHELLS` contains `'agy'`; `resolveShell()` maps `'agy'` to the same shell-wrapped command as `'codex'`; `cd studio && npm run typecheck` exits 0.
**Delivers stories:** S1.1
**Depends on:** Phase 0
**Enables:** Phase 2 — renderer can't launch a terminal kind that the main process rejects
**Details:**
- Add `'agy'` to the `ALLOWED_SHELLS` array. Keep alphabetical order if the array is sorted, otherwise append.
- In `resolveShell()`, add an `'agy'` case alongside `'claude'` and `'codex'`. The resolved command must be:
  - **Windows:** `shell = 'powershell.exe'`, `args = ['-NoExit', '-Command', 'agy']`
  - **non-Windows:** `shell = 'bash'`, `args = ['-c', 'exec agy']`
  - Pattern: mirror the existing `'codex'` case exactly — only change the command string from `'codex'` to `'agy'`.
- Do NOT modify any other code in `terminal.ts`.
**Verify:** `cd studio && npm run typecheck`

---

### Phase 2: Renderer types, store, and launch logic   ← Conversation: 2
**File:** `studio/src/renderer/src/types/terminal.ts`, `studio/src/renderer/src/store/chatStore.ts`, `studio/src/renderer/src/lib/launchTerminal.ts` — MODIFY
**Done when:** All three files compile cleanly; `TerminalKind` includes `'antigravity'` in both type files; `launchTerminal('agy')` resolves to kind `'antigravity'`; `cd studio && npm run typecheck` exits 0.
**Delivers stories:** S2.1
**Depends on:** Phase 1
**Enables:** Phase 3 — UI components depend on the kind being valid
**Details:**

**`types/terminal.ts`:**
- Add `'antigravity'` to the `TerminalKind` union. If it reads `'shell' | 'claude' | 'codex'` change it to `'shell' | 'claude' | 'codex' | 'antigravity'`.

**`chatStore.ts`:**
- Find the `TerminalKind` definition (line ~20). Add `'antigravity'` to the union. Keep it consistent with `types/terminal.ts`.
- If `chatStore.ts` imports `TerminalKind` from `types/terminal.ts` (rather than re-declaring it), the change in `types/terminal.ts` is sufficient — verify before editing.

**`launchTerminal.ts`:**
- In the kind determination chain (line ~21), add `command === 'agy' ? 'antigravity' :` before the final `'shell'` fallback:
  ```typescript
  command === 'claude' ? 'claude'
  : command === 'codex' ? 'codex'
  : command === 'agy'   ? 'antigravity'
  : 'shell'
  ```
- In the prompt patterns object, add an `'antigravity'` entry. Use `['> ']` (same as `claude` and `codex`):
  ```typescript
  antigravity: ['> '],
  ```
- If any switch/if-else on `TerminalKind` exists in `launchTerminal.ts`, add the `'antigravity'` case.

Do NOT touch any other renderer files in this conversation.
**Verify:** `cd studio && npm run typecheck`

---

### Phase 3: UI components and schema   ← Conversation: 3
**File:** `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx`, `studio/src/renderer/src/components/Terminal/BrandIcons.tsx`, `studio/src/renderer/src/lib/studioSchema.ts` — MODIFY
**Done when:** The Antigravity option appears in `TerminalLauncher.tsx`; `BrandIcons.tsx` exports `AntigravityIcon`; `studioSchema.ts` has `'topbar-antigravity'`; `cd studio && npm run typecheck` exits 0.
**Delivers stories:** S3.1, S3.2
**Depends on:** Phase 2 (`'antigravity'` kind must be valid before UI can reference it)
**Enables:** nothing (final phase)
**Details:**

**`BrandIcons.tsx` (do this first — exported before it can be imported):**
- Read the full file first to understand the existing icon component pattern (inline SVG? imported asset? size props?).
- Add `AntigravityIcon` component following the same pattern as `ClaudeIcon` or `CodexIcon`.
- SVG content: the Google G lettermark. Use this minimal SVG path:
  ```tsx
  export function AntigravityIcon({ size = 16 }: { size?: number }) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        {/* Google G mark */}
        <path
          d="M21.35 11.1H12v2.9h5.35C16.8 16.6 14.6 18 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.49 0 2.85.55 3.88 1.45L18.1 5.22A9.93 9.93 0 0 0 12 3C7.03 3 3 7.03 3 12s4.03 9 9 9c5.25 0 9-3.69 9-9 0-.6-.05-1.19-.14-1.76H21.35C21.35 11.08 21.35 11.09 21.35 11.1Z"
          fill="#1967D2"
        />
      </svg>
    );
  }
  ```
  Verify the `#1967D2` hex is Antigravity's brand blue by checking https://antigravity.google — if different, use the correct hex with a comment noting the source. If unable to verify, use `#1967D2` with a TODO comment.

**`TerminalLauncher.tsx`:**
- Read the full file first to understand how the Shell / Claude / Codex options are structured (each is likely a button or menu item with a label and icon).
- Add an Antigravity option following the exact same pattern. The option should:
  - Display label: `"Antigravity"` (or `"agy"` if other labels use short names)
  - Use `AntigravityIcon` from `BrandIcons.tsx`
  - Call `launchTerminal` (or the equivalent) with `command = 'agy'`
- Import `AntigravityIcon` from `BrandIcons.tsx`.

**`studioSchema.ts`:**
- Read the file to understand the topbar item schema shape (lines 55–69).
- Add a `'topbar-antigravity'` item following the same shape as `'topbar-codex'`. Use `label: 'Antigravity'`, `command: 'agy'`, `icon: 'AntigravityIcon'` (or whatever field the schema uses).

**Verify:** `cd studio && npm run typecheck`
After the verify command passes, write `pathly/plans/antigravity-studio/VERIFY.md` with first line `RESULT: PASS` and a one-line summary of the typecheck output.
After done, update PROGRESS.md Conv 3 to DONE and Status to COMPLETE.

---

## Key Decisions
- **No new IPC channel:** `terminal:spawn` already accepts any allowed shell. Adding `'agy'` to `ALLOWED_SHELLS` is sufficient. No preload or IPC changes needed.
- **`resolveShell` mirrors codex:** `agy` is an AI CLI tool like `codex` — it needs the same shell-wrapper treatment on both Windows (PowerShell) and non-Windows (bash -c exec).
- **Prompt pattern `'> '`:** Antigravity CLI's interactive prompt is expected to be `>` (standard for AI CLI tools). If `agy` uses a different prompt (e.g. `agy> `), update `launchTerminal.ts` after verifying.
- **Google G icon, `#1967D2`:** User-confirmed choice. Google primary blue is a safe fallback if Antigravity uses a custom shade.
