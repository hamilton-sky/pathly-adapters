# Implementation Plan — po-mid-conversation-web-research

## Architecture Notes

This is a behavior-only addition to a single agent contract file. No code, no new files, no
skill changes. The PO agent already has access to the sub-agent spawning mechanism used by
other agents (planner, architect). The change teaches the PO when and how to use `type: web`
entries from the scout-flow canonical format — inline during a live conversation turn.

The po.md already has a `## How to behave` section with conversation style rules and a
`## What NOT to do` section. The web research behavior belongs in a new dedicated section
between those two sections so it reads as an extension of how-to-behave rather than an
exception.

## Happy Path

1. User says something that implies an external knowledge gap (competitor named, regulation
   cited, market claim made, domain term used that the PO doesn't know well).
2. PO recognizes the gap, writes a brief note to the user that it is looking this up.
3. PO emits up to 4 `type: web | query: <query>` entries and spawns web-researcher agents
   in parallel.
4. Agents return. PO compresses findings into one short internal summary — not shown verbatim
   to the user.
5. PO continues the conversation using the compressed findings: asks a sharper question,
   names a specific risk, or challenges an assumption the user made.

---

## Pre-flight

Before editing po.md, verify the file is in a clean baseline state:

- Read `src/pathly_data/core/agents/po.md` in full.
- Confirm the file ends with the `## Exit: stop (discard)` section and no mid-conversation
  research section already exists.
- Record the line count as your baseline.

Done when: builder has confirmed baseline line count and no pre-existing web research section.

---

## Phase 1 — Add mid-conversation web research section to po.md

**Stories:** S1, S2, S3

**File:** `src/pathly_data/core/agents/po.md`

**Done when:**
- A new `## Mid-conversation web research` section exists in po.md between `## How to behave`
  and `## What NOT to do`.
- The section contains:
  - When to trigger (judgment call — external knowledge gap detected)
  - The signal line behavior (S1-AC1, S1-AC2)
  - The spawn format: `type: web | query: <search query>`, max 4 entries (S2-AC1, S2-AC3)
  - Explicit prohibition on `type: scout` and `type: quick` (S2-AC2)
  - The compress-then-act instruction: compress to internal summary, then use to sharpen
    questions or surface risks — never dump raw findings (S3-AC1, S3-AC2)
  - The judgment trigger rule: no mandatory phase or question number (S3-AC3)
- All 3 stories' acceptance criteria are satisfied by reading po.md alone (no running required).
