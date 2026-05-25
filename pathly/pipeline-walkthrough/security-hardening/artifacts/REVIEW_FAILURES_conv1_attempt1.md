---
conversation: 1
attempt: 1
phase: review
feature: security-hardening
---

# Review Failures — security-hardening Conv 1

## Verdict: FAIL

Three IPC handlers in `studio/src/main/ipc/terminal.ts` are missing the tabId ownership check that the architecture requires. One handler has an inconsistency with the error-reporting convention.

---

## Violations

### V1 — terminal:resize — Missing ownership guard
**File:** `studio/src/main/ipc/terminal.ts:101-103`
**Rule:** ARCHITECTURE_PROPOSAL.md — "tabId level" ownership trust boundary; all write-like operations on a PTY must verify `ptyOwners.get(tabId) === event.sender.id`
**Description:** `terminal:resize` uses `_event` (unused sender) and calls `pty.resize()` without checking that the caller owns the tab. Any renderer can resize any tab's PTY.

---

### V2 — terminal:kill — Missing ownership guard
**File:** `studio/src/main/ipc/terminal.ts:105-113`
**Rule:** ARCHITECTURE_PROPOSAL.md — tabId ownership trust boundary
**Description:** `terminal:kill` uses `_event` (unused sender) and kills the PTY without verifying ownership. Any renderer can terminate any tab.

---

### V3 — terminal:popout — Missing ownership guard
**File:** `studio/src/main/ipc/terminal.ts:115-151`
**Rule:** ARCHITECTURE_PROPOSAL.md — tabId ownership trust boundary
**Description:** `terminal:popout` uses `_event` (unused sender) and reroutes PTY output to a new window without verifying ownership. Any renderer can hijack any tab's output stream.

---

### V4 — terminal:spawn — Silent no-op on duplicate tabId
**File:** `studio/src/main/ipc/terminal.ts:48`
**Rule:** Internal consistency — all other validation failures in `terminal:spawn` call `event.sender.send('terminal:error', tabId, ...)` before returning; the duplicate-tab early return is silent.
**Description:** `if (activePtys.has(tabId)) return` silently discards the call with no error sent to the renderer, inconsistent with the error-reporting pattern used for every other guard in the same handler.

---

## Pass

- ALLOWED_SHELLS allowlist enforced in `terminal:spawn` — verified at line 51-54
- `isValidCwd` uses `realpathSync` + homedir bounds check — verified at lines 29-36
- `ptyOwners.set` on spawn — verified at line 79
- `ptyOwners.delete` on exit and kill — verified at lines 87, 110
- `terminal:write` guarded by `ptyOwners.get(tabId) !== event.sender.id` — verified at line 97
- No hardcoded credentials or secrets found
- No renderer-supplied strings used as executable paths (Windows always uses `powershell.exe`; POSIX uses allowlist-validated command or `bash` default)
