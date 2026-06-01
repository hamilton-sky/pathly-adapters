# Exploration — studio-terminal-launcher

## Question
Where in the studio Electron app is the code that opens terminals for Claude, Codex, and PowerShell — and what changes are needed to add an Antigravity (`agy`) terminal as a fourth option?

## Scope
- `studio/` — Electron/React frontend only
- Terminal launch / shell spawn code
- Any UI component that renders the "open terminal" buttons

## Out of scope
- `src/pathly_data/` adapter changes (covered by antigravity-adapter plan)
- Backend FSM / orchestrator changes
- IPC beyond what directly relates to terminal spawning

## Success criterion
We can answer: "Which files to create/modify, and what the change looks like" — enough to add a conversation to the antigravity-adapter plan or create a new studio plan.
