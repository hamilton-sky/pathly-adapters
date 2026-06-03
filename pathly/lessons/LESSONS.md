---

---
# LESSONS.md — Active

_Last updated: 2026-06-03 | Sources: 12 features_
_Max 12 lessons. Planner reads this before every plan._

---

## L-001: Run a pre-flight check before Phase 1

### Pattern
Phases assume keys, artifacts, or CLI behaviors that do not yet exist in the live repo. Mid-phase discoveries (missing `conv_start_sha`, broken `pathly-setup` output, failing baseline tests) derail implementation and blur accountability between the feature and prior debt.

### Rule
MUST run a pre-flight check at plan time — verify all assumed keys, file paths, and CLI commands produce expected output before writing acceptance criteria or starting Phase 1.

### Injection
- Add to `IMPLEMENTATION_PLAN.md`: a "Pre-flight" phase (Phase 0) that runs the verify command and records any pre-existing failures as a baseline before Conv 1 begins.
- For any acceptance criterion that invokes a CLI command: run the command during planning and confirm output matches expectations. If it fails, rewrite as a file-existence or schema check.

### Sources
security-fixes, enforcement-gates | Stage: planning/test

---

## L-002: Verify live codebase structure before writing plan paths and acceptance criteria

### Pattern
Plans and acceptance criteria name file paths based on intended structure rather than what exists in the live repo. Builders follow the stated path, tester catches the mismatch — fix cycle required at test time instead of plan time.

### Rule
MUST glob the target directory and confirm the exact file path before writing it in any plan file or acceptance criterion. Core agents live in subdirectories (`research/`, `planning/`, `building/`, `quality/`) — always check which applies.

### Injection
- Before writing `USER_STORIES.md` acceptance criteria: run a glob against the containing directory to confirm path structure matches the live repo.
- For new core agent files: include `frontmatter check` as an explicit sub-criterion — `name:` and `description:` fields must be present.
- In conversation prompts: add a "verify before edit" step — builder globs/reads to confirm the stated path exists before touching any file.

### Sources
docs-sync, adapter-parity | Stage: planning/test

---

## L-003: Every plan phase needs an explicit file path and done-condition

### Pattern
Agents without explicit file paths and done-conditions spend 4–6 tool calls on orientation (reading FEATURE_INDEX, globbing, re-reading the plan) before any real work starts. This compounds across retries and continuation sessions.

### Rule
MUST include a `**File:**` path and `**Done when:**` condition in every phase of every plan, at all rigor levels. Also create `FEATURE_INDEX.md` as the first plan file so builders orient in one read.

### Injection
- Add to every phase in `IMPLEMENTATION_PLAN.md`: `**File:** <exact path>` and `**Done when:** <one observable sentence>`.
- Add to planner output: create `plans/<feature>/FEATURE_INDEX.md` as the first file, before `USER_STORIES.md`.
- Rigor depth: lite = path + done-condition; standard = + verify command; strict = + verify command + rollback note.

### Sources
docs-sync, parallel-scout-standard, agent-architecture-refactor | Stage: planning/implementation

---

## L-004: Gate artifacts (VERIFY.md and REVIEW.md) must be in conversation prompts

### Pattern
The FSM gates require `VERIFY.md` (build→review) and `REVIEW.md` (review→test) as required artifacts. In multiple features, these were not mentioned in the conversation prompts — agents completed their work but didn't write the artifacts, causing gate failures requiring manual resolution mid-pipeline.

### Rule
MUST add the VERIFY.md write instruction to every build conversation prompt's final step, and the REVIEW.md write instruction to every review stage brief.

### Injection
- Add to every build conversation prompt final step: "After verification passes, write `pathly/plans/<feature>/VERIFY.md` with first line `RESULT: PASS` and a one-line summary of what passed."
- Add to every reviewer brief final step: "Write `pathly/plans/<feature>/REVIEW.md` with first line `RESULT: PASS` and a summary of findings. This file is required for the FSM gate to advance to TESTING."

### Sources
enforcement-gates, hq-panel, studio-a11y-p1 | Stage: building/reviewing

---

## L-005: Split conversations when mixing a new service layer with UI component changes

### Pattern
Conversations that pack both a new service/client class AND multiple UI component changes produce scope overload: more review violations, higher builder cost, and harder verification. Two separate concerns compound into a single fragile prompt.

### Rule
MUST scope each building conversation to a single concern category: new service/lib layer OR UI component changes — never both in the same conversation.

### Injection
- Add to conversation breakdown rule: "If a conv touches both a new `lib/` or `hooks/` class AND 2+ component files, split it: Conv N = service layer only, Conv N+1 = component wiring."
- Add to `IMPLEMENTATION_PLAN.md` conversation map notes: flag any conversation that mixes service + UI as a split candidate.

### Sources
hq-panel, brightsky-chat-connect | Stage: planning

---

## CANDIDATE-004: Broad verify scope for "eliminate X" features

### Pattern
A verify command scoped to the files listed in the conversation prompt misses files that also contain the pattern but weren't explicitly named. Tester catches these in a later fix cycle.

### Rule
MUST write the done-condition verify command to cover the entire affected directory, not just the files the conversation explicitly lists.

### Injection
- Add to Conv verify for "replace/eliminate X across all Y" features: `grep -rn 'X' src/<tree>/` — full tree, not per-file.

### Sources
agent-architecture-refactor | Stage: test

---

## CANDIDATE-005: Conversation scope — max 1 file type per conversation

### Pattern
Conversations that batch 3–4 files of the same type (skills, agents) accumulate scope, making verification harder and inconsistencies easier to miss.

### Rule
MUST scope each conversation to at most one file per category. Each phase must carry an explicit file path and done-condition.

### Injection
- Add to `CONVERSATION_PROMPTS.md` splitting rule: "If a conversation touches more than one file of the same type, split into separate conversations — one per file."

### Sources
parallel-scout-standard | Stage: planning

---

## CANDIDATE-006: Embed event schema in IMPLEMENTATION_PLAN

### Pattern
New event types appended to EVENTS.jsonl use inconsistent field names (`ts` vs `timestamp`). Tester catches the mismatch; fix requires adding test assertions for the canonical name.

### Rule
MUST list exact fields for each new event type and cross-reference existing events in the codebase in `IMPLEMENTATION_PLAN.md` before implementation begins.

### Injection
- Add to `IMPLEMENTATION_PLAN.md` for any EVENTS.jsonl-touching phase: a schema block listing each event type and its exact fields.

### Sources
enforcement-gates | Stage: test

---

## CANDIDATE-007: Acceptance criteria for docs stories must not over-specify format

### Pattern
Planner writes acceptance criteria that mix document structure ("use Risk/Mitigation format") with content requirements, causing test failures when the format criterion doesn't match the existing doc style.

### Rule
Docs stories must specify WHAT content to add as acceptance criteria; HOW it is formatted belongs in the conversation prompt, not the story.

### Injection
- In `USER_STORIES.md` for any story touching a docs file: keep criteria to verifiable content facts (section exists, vector described) — not format or style rules.

### Sources
security-fixes | Stage: test

---

## CANDIDATE-008: Security stories need at least one failure-case criterion

### Pattern
Security fixes without an explicit failure-mode criterion pass implementation review but leave the tester verifying only the happy path.

### Rule
Every security story must include at least one criterion of the form "A request/input with [bad value] causes [safe outcome]."

### Injection
- In `USER_STORIES.md` for any security story: add one failure-case criterion specifying a specific attack input and expected safe output.

### Sources
security-fixes | Stage: planning

---

## CANDIDATE-009: Pre-flight CLAUDE.md violation scan for touchpoint files

### Pattern
When a file with pre-existing coding-standard violations (useTheme, inline styles) is listed as a touchpoint, the reviewer flags those violations as in-scope — even if they predated the feature — because the file was modified. This triggers an unplanned fix round.

### Rule
MUST grep each listed touchpoint file for known violation patterns before writing the plan. If violations exist, either add a fix phase to the plan or document them as explicitly accepted tech debt in IMPLEMENTATION_PLAN.md.

### Injection
- Add to Phase 0 in `IMPLEMENTATION_PLAN.md` for any feature touching UI component files: "Scan each touchpoint for pre-existing `useTheme()` calls and `style={{ }}` props. If found, either add a fix phase or note: 'pre-existing violation, accepted as out-of-scope for this feature.'"

### Sources
studio-a11y-p1 | Stage: review

---

## CANDIDATE-010: Include POST body schema for every API endpoint in conversation prompts

### Pattern
Conversation prompts listing only endpoint URLs (no body fields) cause builders to send empty or wrong-field POST bodies, discovered only at runtime.

### Rule
MUST include a `body:` example object alongside every endpoint URL listed in CONVERSATION_PROMPTS.md — URL alone is not a complete API contract.

### Injection
- In the conversation prompt for any feature touching an HTTP API, add a table: `| Endpoint | Method | Required body fields |` with one row per endpoint before the scope list.

### Sources
hq-panel | Stage: implementation
