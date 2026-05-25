---

---
# LESSONS.md — Active

_Last updated: 2026-05-25 | Sources: 7 features_
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

## CANDIDATE-006: VERIFY.md is not auto-created — document the manual step

### Pattern
Gates that require `VERIFY.md` to exist will block pipeline advance. Builders don't know where to write it or in what format; feedback files that trigger on its absence don't explain this.

### Rule
MUST document the `VERIFY.md` path, required first line (`RESULT: PASS`), and an example content block in any conversation prompt that triggers a verify gate.

### Injection
- Add to `CONVERSATION_PROMPTS.md` for any conv with a verify gate: "After the verify command passes, write `plans/<feature>/VERIFY.md` with first line `RESULT: PASS` and a one-line summary."

### Sources
enforcement-gates | Stage: building

---

## CANDIDATE-007: Embed event schema in IMPLEMENTATION_PLAN

### Pattern
New event types appended to EVENTS.jsonl use inconsistent field names (`ts` vs `timestamp`). Tester catches the mismatch; fix requires adding test assertions for the canonical name.

### Rule
MUST list exact fields for each new event type and cross-reference existing events in the codebase in `IMPLEMENTATION_PLAN.md` before implementation begins.

### Injection
- Add to `IMPLEMENTATION_PLAN.md` for any EVENTS.jsonl-touching phase: a schema block listing each event type and its exact fields.

### Sources
enforcement-gates | Stage: test

---

## CANDIDATE-008: Acceptance criteria for docs stories must not over-specify format

### Pattern
Planner writes acceptance criteria that mix document structure ("use Risk/Mitigation format") with content requirements, causing test failures when the format criterion doesn't match the existing doc style.

### Rule
Docs stories must specify WHAT content to add as acceptance criteria; HOW it is formatted belongs in the conversation prompt, not the story.

### Injection
- In `USER_STORIES.md` for any story touching a docs file: keep criteria to verifiable content facts (section exists, vector described) — not format or style rules.

### Sources
security-fixes | Stage: test

---

## CANDIDATE-009: Redundant acceptance criteria confuse the tester

### Pattern
A story criterion logically implied by another criterion gets written explicitly. Tester flags it NOT COVERED when the implementation satisfies the root criterion but not the redundant one.

### Rule
Each acceptance criterion must be independently falsifiable — if B is always true when A is true, drop B.

### Injection
- Before writing `CONVERSATION_PROMPTS.md`: scan each story's acceptance criteria for implied/redundant entries and remove them.

### Sources
security-fixes | Stage: test

---

## CANDIDATE-010: Security stories need at least one failure-case criterion

### Pattern
Security fixes without an explicit failure-mode criterion pass implementation review but leave the tester verifying only the happy path.

### Rule
Every security story must include at least one criterion of the form "A request/input with [bad value] causes [safe outcome]."

### Injection
- In `USER_STORIES.md` for any security story: add one failure-case criterion specifying a specific attack input and expected safe output.

### Sources
security-fixes | Stage: planning
