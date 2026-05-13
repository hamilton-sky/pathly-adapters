# Feature Index — po-planner-separation

## What this feature does

Splits requirements authorship from planning decomposition. The PO agent becomes
the authoritative source of user stories (`PO_NOTES.md`). The planner consumes
that document and decomposes it into conversations — it no longer authors stories
from scratch. The team-flow plan pipeline gains a new PO Phase that gates on
`PO_NOTES.md` presence. Architectural escalation paths are standardized across
planner and tester.

## Files changed

| File | Change |
|---|---|
| `src/pathly_data/core/agents/po.md` | Add STORM_SEED.md richness check, autoFlow mode, and activation fallback table |
| `src/pathly_data/core/skills/team-flow/plan.md` | Insert PO Phase before Stage 2 Phase 1; update planner prompt to consume PO_NOTES.md |
| `src/pathly_data/core/agents/planner.md` | Add PO advisory spawn rule + ARCH_QUESTION escalation rule |
| `src/pathly_data/core/agents/tester.md` | Add ARCH_QUESTION escalation to "What NOT to do" |

## Plan files

| File | Purpose |
|---|---|
| `FEATURE_INDEX.md` | This file — scope and file map |
| `USER_STORIES.md` | Four stories, one per agent/skill file changed |
| `IMPLEMENTATION_PLAN.md` | Two conversations with phases |
| `PROGRESS.md` | Conversation tracking |
| `CONVERSATION_PROMPTS.md` | Ready-to-paste builder prompts |

## Stories

| Story | Title | Conversation |
|---|---|---|
| 1 | PO reads STORM_SEED.md and scales interaction depth | 1 |
| 2 | PO Phase inserted into team-flow/plan Stage 2 | 1 |
| 3 | Planner consults PO for ambiguous stories and escalates architecture | 2 |
| 4 | Tester escalates architectural questions via ARCH_QUESTION | 2 |

## Out of scope

- Changing the `/po` standalone skill behavior (activation path stays separate)
- Adding new plan file formats or rigor levels
- Changing how STORM_SEED.md is written (architect's domain)
- Retroactively updating existing plan files
