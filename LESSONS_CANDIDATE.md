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

---

### Lesson � pathly-observability (2026-06-02)

### Observation
Test acceptance criteria with grep commands had wrong file paths (development/ vs planning/) and case mismatches (phase: vs Phase:). This caused 2 false test failures requiring a full builder fix cycle.

### Rule
SHOULD validate grep/shell verification commands in USER_STORIES.md against actual file paths before handoff to builder. A one-line smoke test at plan time prevents a test-fix loop.

### Injection
- Add to tester.md rigor_contract (standard+): 'Before reporting FAIL, confirm the grep path exists: stat the file first.'
- Add to planner rigor_contract (strict): 'Validate all grep verification commands in USER_STORIES.md against the actual repo structure.'

### Source
Feature: pathly-observability | Stage: testing | Date: 2026-06-02

---

### Lesson � pathly-observability (2026-06-02)

### Observation
fast/auto mode (build -> review auto-chain, PROGRESS.md auto-update) worked perfectly for a 5-conversation pipeline. No regressions, no manual steps needed.

### Rule
MAY use fast/auto mode by default for standard-rigor features with clean tests. It is production-stable.

### Injection
- go.md: 'For standard rigor with no open feedback, default to fast mode unless user requests manual gates.'

### Source
Feature: pathly-observability | Stage: pipeline | Date: 2026-06-02

## [studio-a11y-p1] Pre-flight CLAUDE.md violation scan for touchpoint files

### Pattern
When a file with pre-existing coding-standard violations (useTheme, inline styles) is listed as a touchpoint, the reviewer flags those violations as in-scope — even if they predated the feature — because the file was modified. This triggered an unplanned fix round.

### Rule
MUST grep each listed touchpoint file for known violation patterns before writing the plan. If violations exist, either add a fix phase to the plan or document them as explicitly accepted tech debt with a comment in IMPLEMENTATION_PLAN.md.

### Injection
- Add to Phase 0 in `IMPLEMENTATION_PLAN.md` for any feature touching UI component files: "Scan each touchpoint for pre-existing `useTheme()` calls and `style={{ }}` props. If found, either add a fix phase or note: 'pre-existing violation, accepted as out-of-scope for this feature.'"
- Add to every build conversation prompt: "After verification passes, write `pathly/plans/<feature>/VERIFY.md` with first line `RESULT: PASS` and a one-line summary."

### Source
Feature: studio-a11y-p1 | Stage: review | Date: 2026-06-03

---

## [studio-a11y-p1] FSM gate artifacts must be in conversation prompts

### Pattern
The FSM gates require `VERIFY.md` (build→review) and `REVIEW.md` (review→test) as artifact gates. Neither was documented in the conversation prompts, causing two gate failures requiring manual resolution mid-pipeline.

### Rule
MUST include the VERIFY.md write instruction in every build conversation prompt, and the REVIEW.md write instruction in every review-stage brief.

### Injection
- Add to every build conversation prompt final step: "Write `pathly/plans/<feature>/VERIFY.md` with first line `RESULT: PASS` and a one-line summary of what passed."
- Add to every review brief final step: "Write `pathly/plans/<feature>/REVIEW.md` with first line `RESULT: PASS` and a summary of findings."

### Source
Feature: studio-a11y-p1 | Stage: building/reviewing | Date: 2026-06-03

---

## [agent-done-early-advance] Define reconciliation timeout in USER_STORIES, not analysis

### Pattern
The 30-second billing reconciliation window for early FSM advance was not specified in USER_STORIES.md. Builders discovered it during Conv 2 analysis, leading to the longest build conversation (164K tokens, 820s wall). Reviewers had no AC to validate the timeout against.

### Rule
MUST specify any timing SLAs (timeouts, windows, polling intervals) as explicit acceptance criteria in USER_STORIES.md before build begins. Do not leave "how long" as an analysis-phase discovery.

### Injection
- When a feature involves async wait windows (reconciliation, polling, retry), add AC: "Timeout defaults to X seconds; configurable via [param]."
- In CONVERSATION_PROMPTS.md for the implementing conversation, call out the timeout value explicitly: "Use timeout=30 (configurable via param)."

### Source
Feature: agent-done-early-advance | Stage: planning | Date: 2026-06-04

---

## [agent-done-early-advance] Document inter-flag dependencies in ARCHITECTURE_PROPOSAL.md

### Pattern
The interactive mode constraint (interactive=True requires early_advance=True) was not documented until Conv 4. This forced a design decision mid-conversation about whether to raise RuntimeError vs. warn. Had it been documented in ARCHITECTURE_PROPOSAL.md, the decision would have been made during planning.

### Rule
MUST add an "Inter-flag dependencies" or "Preconditions" section to ARCHITECTURE_PROPOSAL.md for any feature that introduces multiple feature flags. List which flags imply other flags and the failure mode when preconditions aren't met.

### Injection
- Add to ARCHITECTURE_PROPOSAL.md template under "Feature flags": "Preconditions: list flag combinations that are invalid and the expected runtime behavior (RuntimeError / WARNING / silent degradation)."

### Source
Feature: agent-done-early-advance | Stage: architecture | Date: 2026-06-04
