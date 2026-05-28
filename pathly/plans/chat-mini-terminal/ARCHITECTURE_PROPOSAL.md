# Architecture Proposal

## Current State

`OutputSnippet` is a passive renderer of lines collected by `ChatPanel`. It is useful for short status previews but cannot handle interactive prompts.

`TerminalTabView` already proves the correct terminal architecture:

- xterm renders a terminal UI.
- `window.pathly.terminal.onData(tabId, ...)` streams PTY output.
- `xterm.onData(...)` forwards user input to `window.pathly.terminal.write(tabId, data)`.
- resize events update the backend PTY dimensions.

## Proposed State

Add a compact xterm view inside Conductor chat that attaches to an existing terminal tab id.

```text
window.pathly.terminal PTY session
  |
  +-- full bottom TerminalTabView
  |
  +-- chat MiniTerminalCard
```

Both views are clients of the same PTY. Neither owns the process lifecycle by itself.

## Store Changes

Extend terminal state with enough metadata for chat attachment:

- active tab id per terminal kind, or lookup by existing `tabs[].kind`,
- recent scrollback buffer by tab id,
- action to open/select a tab in the full terminal.

The buffer should be renderer-local and capped to avoid unbounded memory growth.

## Component Changes

`MiniTerminalCard` should:

- receive `tabId`, `target`, `status`, and optional preview lines,
- mount its own xterm instance,
- replay recent buffered output,
- subscribe to live output,
- forward keyboard input to the PTY,
- fit to its compact container,
- expose collapse and open-full-terminal controls.

## Lifecycle Rules

- Collapsing the card disposes the mini xterm view only.
- Closing the card does not kill the terminal tab.
- The existing bottom terminal keeps owning explicit tab close/kill behavior.
- If no tab id exists yet, the card can show the old passive waiting state.

## Risks And Mitigations

- Duplicate output risk: replay only buffered historical data once, then subscribe to live data.
- Focus confusion: show a visible focus ring and keep terminal input visually distinct from Conductor chat input.
- Layout instability: use fixed min/max height and compact terminal font.
- Process ownership confusion: only the full terminal close action kills tabs.
