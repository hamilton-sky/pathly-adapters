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

## Story 4 - Manage Terminal Instances

As a user, I want to see and control all open terminal instances from the full
terminal, so hidden chat/full views do not make me lose a running process.

Acceptance criteria:

- Full terminal tab actions are visible without hover.
- X hides a terminal view without killing the PTY.
- Bin kills/disposes/removes the terminal instance.
- A hamburger button opens and closes the right-side instance rail.
- The instance rail can focus/show, hide, and kill each open terminal.

Delivered by: Conversation 3.

## Story 5 - Recognize Runtime Targets

As a user, I want Shell, Claude, and Codex to use consistent icons everywhere,
so terminal targets are recognizable in the header, launcher, cards, tabs, and
instance rail.

Acceptance criteria:

- Shell uses the shared terminal badge icon.
- Claude uses the shared Claude badge icon.
- Codex uses the shared Codex badge icon.
- The Conductor header dot turns active for shell/PowerShell the same way it
  does for Claude and Codex when an instance exists.

Delivered by: Conversation 3.
