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
