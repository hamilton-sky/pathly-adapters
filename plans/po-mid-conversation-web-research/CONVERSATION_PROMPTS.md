# Conversation Prompts — po-mid-conversation-web-research

## C1 — Add web research behavior to po.md

Read `plans/po-mid-conversation-web-research/FEATURE_INDEX.md` first, then
`plans/po-mid-conversation-web-research/IMPLEMENTATION_PLAN.md`, then
`plans/po-mid-conversation-web-research/USER_STORIES.md`.

### Pre-flight

Read `src/pathly_data/core/agents/po.md` in full. Confirm it ends with the
`## Exit: stop (discard)` section and that no mid-conversation web research section already
exists. Record the current line count as your baseline before making any edits.

### Task

Add a `## Mid-conversation web research` section to `src/pathly_data/core/agents/po.md`.
Place it between the `## How to behave` section and the `## What NOT to do` section.

The section must cover all of the following — in plain prose or a short list, no headers
inside the section needed:

1. **When to trigger** — the PO uses its own judgment when it detects an external knowledge
   gap: a competitor is named, a regulation is cited, a market claim is made, or a domain term
   is used that the PO does not know well. There is no mandatory trigger rule based on session
   phase or question number.

2. **Signal the user first** — before spawning any agents, write a brief plain-language note
   in the same response turn (e.g. "Let me look that up..."). The signal appears in the same
   turn as the research trigger, not before or after.

3. **Spawn format** — use `type: web | query: <search query>` entries only. Maximum 4 entries
   per trigger. Spawn all entries in parallel.

4. **Prohibited types** — `type: scout` and `type: quick` must never be used by the PO.

5. **Compress then act** — after receiving findings, compress them into a short internal
   summary. Do not dump raw search results to the user. Use the summary to ask a sharper
   question, name a specific risk, or challenge an assumption — the research must produce a
   concrete insight in the conversation.

### Done when

- `src/pathly_data/core/agents/po.md` contains a `## Mid-conversation web research` section
  in the correct position (between `## How to behave` and `## What NOT to do`).
- All five content requirements above are present and unambiguous in the section text.
- All other existing sections in po.md are unchanged.
- Stories S1, S2, S3 acceptance criteria are all satisfied by reading po.md alone.

Update `plans/po-mid-conversation-web-research/PROGRESS.md` to mark C1, S1, S2, S3 as done.
