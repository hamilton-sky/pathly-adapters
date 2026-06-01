---
name: Architecture Proposal
---
# antigravity-studio — Architecture Proposal

## No new IPC channels needed

The existing `terminal:spawn` IPC channel already accepts any command string — the only guard is the `ALLOWED_SHELLS` allowlist. Adding `'agy'` to that list is all the main-process wiring needed. The preload bridge, the `terminal:data` stream, `terminal:write`, `terminal:resize`, and `terminal:kill` all work unchanged.

## `resolveShell()` pattern: mirror codex

`agy` is an AI coding CLI tool launched the same way as `codex`:
- **Windows:** Wrapped in `powershell.exe -NoExit -Command agy` — required because Electron's PTY on Windows needs a shell host; `agy` cannot be spawned directly as a PTY on Windows without it.
- **Linux/macOS:** Wrapped in `bash -c exec agy` — the `exec` replaces the bash process with `agy`, keeping the PTY clean.

## Kind system: `'antigravity'` not `'agy'`

The kind is named after the product (`'antigravity'`), not the binary (`'agy'`). This matches the existing pattern:
- binary `claude` → kind `'claude'`
- binary `codex` → kind `'codex'`
- binary `agy` → kind `'antigravity'`

The kind name is used in type unions, store keys, CSS selectors, and icon lookups — it should be readable and match the product name, not the CLI shorthand.

## Icon: Google G inline SVG, `#1967D2`

**Why inline SVG:** `ClaudeIcon` and `CodexIcon` are inline SVG components (not imported image files). Following the same pattern avoids adding binary assets, keeps the bundle small, and makes the icon tree-shakeable.

**Why Google G:** User-confirmed choice. The Google G is the most recognisable Antigravity brand mark (Antigravity is a Google product). The simple G lettermark renders cleanly at 16px tab size.

**Color `#1967D2`:** Google's primary blue, used across Google developer products. If Antigravity has a distinct brand blue, update this value after checking the Antigravity brand page.

## Where the brand color token should live

Ideally `#1967D2` should be a CSS token (`--color-antigravity-brand`) in `studio/src/renderer/src/styles/tokens.css`, the same way `--bg-terminal` is defined per palette. However, for v1 the hex can be hardcoded in the SVG fill with a TODO comment — adding the token is a small follow-up cleanup.
