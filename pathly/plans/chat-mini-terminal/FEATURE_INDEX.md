# chat-mini-terminal

## Summary

Add an interactive mini terminal to Conductor chat so users can respond to Claude/Codex/shell prompts without opening the full bottom terminal.

## Plan Files

- `USER_STORIES.md` - user-facing behavior and acceptance criteria.
- `IMPLEMENTATION_PLAN.md` - phased engineering plan.
- `CONVERSATION_PROMPTS.md` - build prompts for Pathly conversations.
- `PROGRESS.md` - current implementation status.
- `ARCHITECTURE_PROPOSAL.md` - cross-component terminal sharing design.

## Current Status

Implemented and verified. The feature now includes an interactive Conductor
mini terminal, shared xterm ownership with the full terminal, hide-vs-kill
terminal semantics, a hamburger-controlled full-terminal instance rail, and
consistent Shell/Claude/Codex runtime icons.
