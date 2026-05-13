# User Stories — po-mid-conversation-web-research

## S1 — PO signals before researching

**As** the PO agent,
**I want** to tell the user I am about to do a web search before I spawn any agents,
**so that** the user knows why there is a brief pause and what is being looked up.

**Acceptance criteria:**
- AC1: When the PO decides to trigger web research, its response in that turn includes a plain-language line stating it is researching before the findings appear (e.g. "Let me look that up...").
- AC2: The signal appears in the same turn that research is triggered — not in a prior or later turn.

**Delivered by:** C1

---

## S2 — PO spawns only type: web agents, never type: scout or type: quick

**As** the PO agent,
**I want** to spawn web-researcher agents using `type: web | query: <search query>` entries,
**so that** I never attempt codebase reads or single-file lookups that are outside my scope.

**Acceptance criteria:**
- AC1: The po.md section describing mid-conversation research states `type: web` as the only permitted entry type.
- AC2: The po.md section explicitly states that `type: scout` and `type: quick` entries must never be used by the PO.
- AC3: The section states a maximum of 4 `type: web` entries per research trigger.

**Delivered by:** C1

---

## S3 — PO uses findings to sharpen questions or surface risks

**As** the user,
**I want** the PO to compress web findings into its conversation and act on them,
**so that** the research delivers a concrete insight — a sharper question, a surfaced risk, or a challenged assumption — rather than just repeating what it found.

**Acceptance criteria:**
- AC1: The po.md section states that after receiving findings the PO must compress them into an internal summary before continuing.
- AC2: The po.md section states the PO must use findings to ask a sharper question, surface a risk, or challenge an assumption — not to dump raw search results to the user.
- AC3: The po.md section states the PO's judgment determines when to trigger research; there is no mandatory trigger rule based on session phase or question number.

**Delivered by:** C1
