# chat-mini-terminal Storm Seed

## Decision

Replace the passive chat output snippet with an interactive mini terminal card that attaches to the same terminal tab/session used by the full Pathly terminal. Keep the full terminal unchanged.

## Live Code Context

- `ChatPanel/index.tsx` subscribes to terminal output and renders `OutputSnippet` cards for Claude, Codex, and shell output.
- `OutputSnippet.tsx` is a passive transcript preview; it cannot accept input.
- `Terminal/TerminalTabView.tsx` already wraps xterm, subscribes to `window.pathly.terminal.onData(tabId, ...)`, and writes input through `window.pathly.terminal.write(tabId, data)`.
- `launchTerminal.writeToTerminal(...)` already returns the tab id after spawning/finding the target session.
- `terminalStore.ts` tracks terminal tabs by id/kind but does not expose a reusable output buffer.

## Architecture Direction

Do not move the full terminal's xterm DOM into chat. Instead, create a separate compact xterm instance in the chat panel that mirrors the same PTY session.

The PTY remains the source of truth:

```text
terminal PTY tab id
  |-- full bottom terminal xterm
  `-- chat mini terminal xterm
```

Both views should:

- receive the same terminal output stream,
- write user keystrokes to the same PTY,
- preserve the full terminal as the primary workspace terminal,
- keep Conductor chat input separate from terminal input.

## Risks

- A mini xterm mounted after output has already streamed needs recent scrollback, or it will appear empty.
- Two xterm views writing to the same PTY is acceptable, but focus must be obvious so chat messages are not accidentally sent to the terminal.
- Fitting xterm in a narrow panel can be brittle; the mini terminal needs fixed height, compact font, and resize refit behavior.
- Closing/collapsing the mini view must not kill the underlying terminal tab.

## Implementation Shape

1. Add terminal scrollback buffering keyed by tab id in renderer state.
2. Add a reusable compact xterm component for the chat card.
3. Replace expanded `OutputSnippet` with an interactive `MiniTerminalCard`.
4. Add "open full terminal" behavior that focuses/opens the existing bottom terminal tab.
5. Keep collapsed preview lightweight for chat readability.
