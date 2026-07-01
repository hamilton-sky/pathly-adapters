---
name: Edge Cases
---
# antigravity-studio — Edge Cases

## EC-1: `agy` binary not installed
**Trigger:** User clicks the Antigravity terminal button but `agy` is not in PATH.
**Risk:** PTY spawn fails silently or crashes the tab.
**Mitigation:** The PTY spawn failure will surface as shell error output in the xterm panel (same behaviour as clicking Codex when Codex is not installed). No app crash. Add a comment in the terminal tab's error state if this pattern is already handled.
**Test:** Manual test — open Antigravity terminal on a machine without `agy`.

## EC-2: Exhaustive switch on TerminalKind misses `'antigravity'`
**Trigger:** Any switch/if-else in the codebase that is exhaustive on `TerminalKind` does not handle the new `'antigravity'` variant.
**Risk:** TypeScript compile error, or runtime fall-through to wrong branch.
**Mitigation:** `npm run typecheck` in every conversation will surface missing cases as TypeScript errors. Builder must fix all reported errors before marking the conversation DONE.
**Test:** Typecheck verify command catches this automatically.

## EC-3: `chatStore.ts` re-declares TerminalKind independently
**Trigger:** `chatStore.ts` has its own `type TerminalKind = 'claude' | 'codex' | 'shell'` instead of importing from `types/terminal.ts`.
**Risk:** After updating `types/terminal.ts`, chatStore.ts still uses the old 3-value union, causing type mismatches when `'antigravity'` is passed.
**Mitigation:** Conversation 2 prompt explicitly instructs the builder to read `chatStore.ts` first and check whether it imports or re-declares. If it re-declares, edit that file too.
**Test:** `npm run typecheck` catches this.

## EC-4: BrandIcons icon size/style doesn't match other icons
**Trigger:** `AntigravityIcon` uses different size props or SVG attributes than `ClaudeIcon` / `CodexIcon`.
**Risk:** Icon renders at wrong size on the tab bar.
**Mitigation:** Conversation 3 prompt instructs the builder to read `BrandIcons.tsx` first and follow the exact same pattern as existing icons.
**Test:** Visual check — compare icon size to ClaudeIcon and CodexIcon in the studio.

## EC-5: Studio CLAUDE.md rules violated (inline styles, component size)
**Trigger:** Builder adds inline `style={{}}` props or a component that exceeds the line limit defined in `studio/CLAUDE.md`.
**Risk:** Code review failure; CI lint failure.
**Mitigation:** Conversation 3 prompt reminds builder to follow `studio/CLAUDE.md` rules (no inline styles, component size limit). Use CSS module classes or existing tokens for the icon color.
**Test:** Reviewer checks for inline styles and component size.

## EC-6: `agy` prompt pattern is not `'> '`
**Trigger:** Antigravity CLI uses a different interactive prompt (e.g. `agy> ` or `◆ `).
**Risk:** `launchTerminal.ts` waits for `'> '` that never comes, blocking auto-command injection.
**Mitigation:** The prompt pattern in `launchTerminal.ts` is a one-line change if the real prompt differs. Document a TODO comment in the code: `// TODO: verify agy prompt pattern — update if different from '> '`. A human can verify by running `agy` interactively.
**Test:** Manual check — open an agy terminal in studio and observe the actual prompt.
