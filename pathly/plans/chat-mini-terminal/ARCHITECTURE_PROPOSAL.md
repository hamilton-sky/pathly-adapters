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
  +-- xtermRegistry record per tabId
      |
      +-- full bottom TerminalTabView host
      |
      +-- chat MiniTerminalCard host
```

The full terminal and chat card do not create duplicate terminal emulators. They
reparent one shared xterm instance per `tabId`; only one host owns the DOM at a
time. The PTY process is separate and remains alive until a bin/kill action is
used.

## Store Changes

Extend terminal state with enough metadata for chat attachment:

- active tab id per terminal kind, or lookup by existing `tabs[].kind`,
- recent scrollback buffer by tab id,
- action to open/select a tab in the full terminal,
- hidden tab ids for "close view but keep process alive" behavior.

The buffer should be renderer-local and capped to avoid unbounded memory growth.

## Component Changes

`MiniTerminalCard` should:

- receive `tabId`, `target`, `status`, and optional preview lines,
- attach the shared xterm instance through `xtermRegistry`,
- release ownership when the full terminal is showing the same tab,
- forward keyboard input through the shared xterm/PTY path,
- fit to its compact container,
- expose collapse, open-full-terminal, hide, and kill controls.

`Terminal` should:

- keep full-tab actions visible without hover,
- expose popout, hide, and kill actions on each tab,
- provide a hamburger-controlled right-side instance rail,
- let the rail focus/show, hide, or kill each terminal instance.

## Lifecycle Rules

- Collapsing the card detaches the card host but keeps the shared xterm and PTY.
- Closing/hiding the card or full tab view does not kill the terminal tab.
- Bin actions in either the card, tab header, or instance rail kill the PTY,
  dispose the shared xterm, and remove the tab.
- If no tab id exists yet, the card can show the old passive waiting state.

## Risks And Mitigations

- Duplicate output risk: solved by one `xtermRegistry` writer/owner per `tabId`
  instead of separate full/card xterm writers.
- Focus confusion: show a visible focus ring and keep terminal input visually distinct from Conductor chat input.
- Layout instability: use fixed min/max height and compact terminal font.
- Process ownership confusion: use X for hide/view-close and bin for kill/remove
  everywhere.
