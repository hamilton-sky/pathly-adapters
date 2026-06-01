# chat-mini-terminal PO Notes

## Problem

When Pathly/Claude/Codex asks for interactive input, the Conductor panel currently shows terminal output but the user must move to the bottom terminal to answer. This breaks the chat-driven workflow.

## Goal

Let users continue a running Pathly process directly from the Conductor chat panel through a compact interactive terminal, without removing or replacing the full Pathly terminal.

## Users

- Pathly Studio users running Claude/Codex/shell commands from Conductor.
- Users who prefer staying in the right-side chat panel while responding to prompts.

## In Scope

- Interactive mini terminal card inside the Conductor chat panel.
- Attach the card to the same Claude/Codex/shell terminal tab used by the full terminal.
- Keep the existing full bottom terminal and its tabs.
- Allow terminal input in the mini card.
- Provide a control to open/focus the full terminal.
- Preserve collapsed preview behavior so chat does not become too noisy.

## Out of Scope

- Removing the bottom terminal.
- Replacing all terminal UI with the chat terminal.
- Multi-pane split support inside the chat card.
- Rebuilding the terminal backend.

## Acceptance Criteria

- After Conductor runs a command, the chat panel shows an interactive terminal card for the active target.
- Typing into the mini terminal writes to the same PTY session.
- Output appears in both the mini terminal and the full bottom terminal.
- Collapsing the mini terminal does not stop the process.
- The full terminal can still be opened and used normally.
- Existing chat input remains usable for Conductor messages.
