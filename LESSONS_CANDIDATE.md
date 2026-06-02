# Lessons Candidate

Extracted from completed features. Run `/pathly lessons` to promote to active memory.

---

## From: studio-ai-chat (2026-05-27)

- **Acceptance criteria enforce pipeline discipline.** Explicit AC for each story made scope violations obvious and gave reviewers unambiguous gate signals. Without AC, 3 scope gate failures would have become subjective arguments.

- **Static schema beats runtime scanning.** Building a typed, constant `studioSchema.ts` instead of parsing the DOM at runtime eliminated a class of flaky automation bugs and made element mapping fully testable without mocking the browser.

- **Embedding models buy responsiveness for free.** MiniLM (transformers.js) delivered sub-50ms skill matching with zero server cost — and doubled as the automation label-matcher in Conv 7's 3-tier cascade.

- **Scope gates need exemption rules for build artifacts.** `tsconfig.tsbuildinfo` and generated type files should never trigger scope violations. Add a category filter to the gate before the first review cycle — 6 gate failures over 5 conversations wasted orchestration time.

- **Budget AI context tokens early.** By Conv 6, every chat request included FSM state + skills list + studioSchema. Agree on a context budget in Conv 0 to prevent bloat before it hits token limits.

---

## [fsm-friction-fixes] Wire mechanism and its trigger in the same conversation

### Pattern
A new FSM counter mechanism was implemented in Conv 3 but its trigger action (`update_progress: mark: conv_done` in the `BUILDING->REVIEWING` transition) was not wired into the flow YAML in the same conversation — the pipeline could not advance via `on_state_counter` in production.

### Rule
MUST include the flow-YAML wiring in the same conversation that introduces a new FSM rule or counter mechanism. Never split mechanism from trigger across conversations.

### Injection
- In the Conv N task list that introduces a new FSM rule, add: "Wire the trigger action for this rule into `team.flow.yaml` in the same conversation (e.g. `update_progress: mark: <field>` on the preceding transition)."

### Source
Feature: fsm-friction-fixes | Stage: implementation | Date: 2026-06-01

---

## [fsm-friction-fixes] Log builder token costs at session close

### Pattern
Builder token costs for Convs 1–3 were not captured because sessions ran without `log-agent-done` calls. This left 28% of the pipeline cost unaccounted in the retro.

### Rule
MUST invoke `log-agent-done` at the close of every building session, even if token counts must be estimated.

### Injection
- Add to every building session's closing step: "Run `log-agent-done` with agent=builder, feature, conversation, result=DONE, and token/duration data from the `<usage>` block."

### Source
Feature: fsm-friction-fixes | Stage: implementation | Date: 2026-06-01

---

## [hq-panel] Include POST body schema for every API endpoint in the plan

### Pattern
Every runner button sent an empty POST body because CONVERSATION_PROMPTS.md only listed endpoint URLs, never body fields. The correct body schema was discovered at runtime by reading `http_server.py`. This also caused a field-name mismatch (`choice` vs `decision`) that wasn't caught until live testing.

### Rule
MUST include a `body:` example object alongside every endpoint URL listed in CONVERSATION_PROMPTS.md — URL alone is not a complete API contract.

### Injection
- In the conversation prompt for any feature touching an HTTP API, add a table: `| Endpoint | Method | Required body fields |` with one row per endpoint before the scope list.
- Example row: `| /runner/start | POST | { topic, flow, project_root, max_iterations, max_cost_usd } |`

### Source
Feature: hq-panel | Stage: implementation | Date: 2026-06-01

---

## [hq-panel] Split wide conversations — rename, store, and new components are three separate conversations

### Pattern
Conv 1 packed a folder rename, a new Zustand store, and three new component trees into a single 64K-token conversation. The overloaded scope produced 9 review violations that a narrower prompt would have avoided. A more focused Conv 1 would have been cheaper and cleaner.

### Rule
MUST scope each building conversation to a single concern category: rename/move OR new store layer OR new component tree. Never combine all three in one prompt.

### Injection
- When planning a feature that includes both a structural refactor (rename/move) and new components, create at least two conversations: Conv N for rename/move only, Conv N+1 for new components.

### Source
Feature: hq-panel | Stage: planning | Date: 2026-06-01

---

## [hq-panel] Reviewer exit contract must include writing REVIEW.md

### Pattern
The FSM gate blocked REVIEWING→TESTING because REVIEW.md was missing — the reviewer completed its work but didn't write the required artifact. The plan didn't specify REVIEW.md as a required output of the review stage.

### Rule
MUST add "write pathly/plans/<feature>/REVIEW.md with round number + PASS/FAIL verdict" to the reviewer's done criteria in every CONVERSATION_PROMPTS.md review section.

### Injection
- Add to every reviewer section in CONVERSATION_PROMPTS.md: "Write `pathly/plans/<feature>/REVIEW.md` summarising the round (N violations, verdict PASS/FAIL). This file is required for the FSM gate to advance to TESTING."

### Source
Feature: hq-panel | Stage: review | Date: 2026-06-01

---

## [brightsky-chat-connect] Multi-conversation TESTING gate missing

### Pattern
FSM advanced to TESTING after Conv 1 review passed, before Conv 2 was built, causing a gate failure and wasted bounce-back.

### Rule
MUST explicitly state in the plan which conversation number gates TESTING entry; do not rely on implicit sequencing.

### Injection
- Add to IMPLEMENTATION_PLAN.md under "Pipeline gates": "TESTING gate: blocked until Conv N (final conversation) is DONE."

### Source
Feature: brightsky-chat-connect | Stage: planning | Date: 2026-06-02

---

## [brightsky-chat-connect] Over-stuffed conversation causes multi-pass builder

### Pattern
Conv 2 packed WebSocket client + UI wiring (5 phases, 6 stories) into one conversation, requiring two builder passes and 87% of total cost.

### Rule
MUST split conversations when a single conversation contains both a new service/client class AND multiple UI component changes — these are different cognitive domains.

### Injection
- Add to conversation breakdown: "If a conv touches both a new lib/ class and 2+ components, split it."

### Source
Feature: brightsky-chat-connect | Stage: planning | Date: 2026-06-02
