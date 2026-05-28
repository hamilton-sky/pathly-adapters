# User Stories

## Story 1 - Respond From Chat

As a Pathly Studio user, I want the Conductor panel to show a real terminal input area when a Pathly command is running, so I can answer prompts without moving to the bottom terminal.

Acceptance criteria:

- The mini terminal appears for the target that Conductor ran.
- The mini terminal accepts keyboard input.
- Submitted input reaches the same Claude/Codex/shell process.
- Terminal output continues to appear while the process is running.

Delivered by: Conversation 1.

## Story 2 - Keep Full Terminal Available

As a user, I want the full bottom terminal to remain available, so I can switch to a larger workspace when needed.

Acceptance criteria:

- The existing bottom terminal remains unchanged.
- A control in the mini terminal opens/focuses the full terminal.
- Collapsing the mini terminal does not kill the terminal process.

Delivered by: Conversation 1.

## Story 3 - Preserve Chat Usability

As a user, I want the chat panel to remain readable, so terminal output does not overwhelm Conductor messages.

Acceptance criteria:

- The mini terminal has a compact fixed height.
- Collapsed mode shows a lightweight preview.
- Chat input remains separate from terminal input.
- The user can clearly tell whether focus is in chat input or terminal input.

Delivered by: Conversation 2.
