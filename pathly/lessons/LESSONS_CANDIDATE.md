---

---
# Lessons Candidate

Patterns extracted from retros. Promote to LESSONS.md via `/lessons`.

---

## [studio-polish] Pyright re-export: use `import X as X` in shim modules

### Pattern
When creating a thin shim module (`from .cli import main`), Pyright's `reportMissingImports` fires when the re-exported name is consumed via `from shim import name`. Fix: use `from .cli import main as main` — the `as X` pattern signals an explicit re-export to Pyright.

### Source
studio-polish retro, 2026-05-25

---

## [studio-polish] Name every function by file in refactor stories before building

### Pattern
A refactor story that says "module X becomes a thin shim" is ambiguous. The builder left `main()` in the wrong file, requiring one ARCH_FEEDBACK cycle. Fix: list each function's destination file by name in the story's acceptance criteria.

### Source
studio-polish retro, 2026-05-25

---

## [docs-sync] Builder acts on plan-baked facts instead of re-verifying live paths

### Pattern
Builder agents edit files based on paths provided in the conversation prompt without first confirming those paths exist and are current in the live repo, causing incorrect edits and multiple review cycles.

### Rule
MUST include an explicit "verify before edit" step in every conversation prompt that touches paths, module names, or entry points — instructing the builder to glob/read the live repo and correct any discrepancy before making changes.

### Injection
- Add to `CONVERSATION_PROMPTS.md` preamble: "Before making any edits, verify the following paths exist in the live repo: `[list paths]`. Correct any discrepancy between the plan's stated paths and reality before proceeding."
- Add to `IMPLEMENTATION_PLAN.md` phase header: "Criticality: low/medium/high — high means extra verification step required."

### Source
Feature: docs-sync | Stage: implementation | Date: 2026-05-11

---

## [docs-sync] No feature-folder index causes agent orientation overhead

### Pattern
Agents spend multiple tool calls globbing and reading plan files to orient themselves because there is no single entry point that lists all files in the feature folder and their roles.

### Rule
MUST create a `FEATURE_INDEX.md` in every feature folder at planning time, listing every plan file with a one-line description of its role and which agent reads it.

### Injection
- Add to planner output: create `plans/<feature>/FEATURE_INDEX.md` as the first file, before USER_STORIES.md.
- Template entry: `| File | Written by | Read by | Purpose |` — one row per plan file.

### Source
Feature: docs-sync | Stage: planning | Date: 2026-05-11

---

## [docs-sync] Implementation plan phases not aligned to PROGRESS.md rows

### Pattern
The implementation plan lists fixes as prose phases but PROGRESS.md tracks at the conversation level, leaving no task-level bridge. The planner fills PROGRESS.md manually, creating drift between the plan and actual tracked work.

### Rule
MUST map each IMPLEMENTATION_PLAN phase to exactly one PROGRESS.md conversation row — one phase = one conversation = one builder prompt.

### Injection
- Add to `IMPLEMENTATION_PLAN.md` template: each phase header must carry a `Conversation: N` tag that matches the corresponding row in PROGRESS.md.
- Add to planner instructions: "After writing IMPLEMENTATION_PLAN.md, verify that every phase maps to exactly one row in PROGRESS.md before writing CONVERSATION_PROMPTS.md."

### Source
Feature: docs-sync | Stage: planning | Date: 2026-05-11

---

## [parallel-scout-standard] Multi-file conversations are too large for reliable builder execution

### Pattern
Conversations that touch 3–4 files of the same type (skills, agents) accumulate too much scope, making it harder to verify and easier to introduce inconsistencies across files.

### Rule
MUST scope each conversation to at most one file per category — one skill file or one agent file per conversation, not a batch. Each phase must carry an explicit file path and done-condition at all rigor levels (lite included).

### Injection
- Add to `CONVERSATION_PROMPTS.md` splitting rule: "If a conversation touches more than one file of the same type (skill, agent, config), split into separate conversations — one per file."
- Add to each phase in `IMPLEMENTATION_PLAN.md`: `**File:** <exact path>` and `**Done when:** <observable condition>` — required at all rigor levels.

### Source
Feature: parallel-scout-standard | Stage: implementation | Date: 2026-05-11

---

## [parallel-scout-standard] Pre-loading file paths and done-conditions eliminates agent orientation overhead

### Pattern
Agents without explicit file paths and done-conditions in their task spend 4–6 tool calls on orientation (reading FEATURE_INDEX, globbing for files, re-reading the plan to understand "done") before any real work starts. This compounds across retries and continuation sessions.

### Rule
MUST include an explicit `File:` path and `Done when:` condition in every phase of every plan, at all rigor levels — not just standard/strict. The planning cost is paid once; the orientation savings are paid on every builder run.

### Injection
- Add to every phase in `IMPLEMENTATION_PLAN.md`: `**File:** <exact path to file being created/modified>` and `**Done when:** <one observable sentence — what is true when this phase is complete>`.
- Depth scales by rigor: lite = path + done-condition; standard = + verify command; strict = + verify command + rollback note.

### Source
Feature: parallel-scout-standard | Stage: retro discussion | Date: 2026-05-11

---

## [parallel-scout-standard] Flow diagram template not offered for orchestration features

### Pattern
Features that introduce new calling conventions or orchestration patterns (like scout-flow) benefit from a visual flow diagram during planning, but the plan skill only offers ASCII diagrams and does not prompt for one when the feature is orchestration-heavy.

### Rule
MUST offer the flow diagram template when a feature introduces a new inter-agent calling convention, sub-skill, or orchestration pattern.

### Injection
- Add to `plan.md` Step 2 (Understand The Feature): "If the feature introduces a new calling convention, sub-skill, or orchestration pattern, include a `FLOW_DIAGRAM.md` regardless of rigor level."

### Source
Feature: parallel-scout-standard | Stage: planning | Date: 2026-05-11

---

## [agent-architecture-refactor] Narrow verify scope misses files not named in the conversation prompt

### Pattern
Conv 1 listed 8 explicit skill files and scoped its verify command to only those files. team/plan.md also had scout-path references but was not in the prompt's file list — the verify command passed, but the tester caught 4 residual references at test time, requiring an extra fix cycle.

### Rule
MUST write the done-condition verify command to cover the entire affected directory, not just the files the conversation explicitly lists. For "replace X across all skills" features, grep the full `src/pathly_data/core/skills/` tree — a miss in the file list is still caught.

### Injection
- Add to Conv 1 verify in `CONVERSATION_PROMPTS.md`: "grep -rn 'scout-path' src/pathly_data/core/skills/ — expected: no output" (full tree, not per-file)
- Add to plan phase template: "Verify scope: if the feature eliminates a pattern globally, the done-condition must grep the entire affected tree, not the explicit file list."

### Source
Feature: agent-architecture-refactor | Stage: test | Date: 2026-05-13

---

## [agent-architecture-refactor] YAML capability expansions need a cross-file audit verify step

### Pattern
After adding `can_spawn` to multiple YAML files across claude/ and codex/ adapters, there is no verify command that confirms all YAML files are consistent. A missed file would compile silently but cause a runtime capability mismatch between adapters.

### Rule
MUST include a single grep that covers all adapter YAML files for the changed field whenever a capability field (can_spawn, can_read, can_write) is added or modified across multiple adapter targets.

### Injection
- Add to any YAML-touching conversation: "Verify: grep -rn 'can_spawn' src/pathly_data/adapters/ — confirm all adapter variants are consistent, not just the ones the conversation touched."

### Source
Feature: agent-architecture-refactor | Stage: implementation | Date: 2026-05-13

---

## [enforcement-gates] Pre-flight manifest scan before Phase 1

### Pattern
Features that depend on existing codebase keys (e.g. `conv_start_sha` in STATE.json) assume those keys exist. When they don't, unplanned prerequisite work interrupts mid-phase.

### Rule
MUST scan all assumed keys/fields and patch gaps as a standalone prerequisite before Phase 1 — not as mid-phase discoveries.

### Source
Feature: enforcement-gates | Stage: planning | Date: 2026-05-25

---

## [enforcement-gates] Gate artifact feedback must say WHERE to write the artifact

### Pattern
When a gate fails because an artifact is missing (e.g. `VERIFY.md`), the feedback file tells the builder the file is missing but not where to write it or in what format. Builders must infer this from gate config.

### Rule
MUST include in the gate `on_fail` feedback file: the expected path, the required first line, and an example content block.

### Source
Feature: enforcement-gates | Stage: building | Date: 2026-05-25

---

## [enforcement-gates] Embed event schema in IMPLEMENTATION_PLAN

### Pattern
GATE_FAILED and GATE_SKIPPED events were appended without `schema_version`. The tester caught a `ts` vs `timestamp` naming mismatch. No cross-reference to existing events existed in the plan.

### Rule
MUST list exact fields for each new event type and cross-reference existing events in the codebase in IMPLEMENTATION_PLAN before implementation begins.

### Source
Feature: enforcement-gates | Stage: testing | Date: 2026-05-25

---

## [enforcement-gates] Hardcode scope-file parsing rules, not prose descriptions

### Pattern
"Lines starting with `-` or backtick" is ambiguous. Loose parsing silently produces zero declared paths, causing GATE_SKIPPED when enforcement was expected.

### Rule
MUST specify the exact regex or parsing algorithm in the plan, not prose descriptions. Include a test case in Phase 1 that verifies the parser produces non-empty output on a representative input.

### Source
Feature: enforcement-gates | Stage: implementation | Date: 2026-05-25

---

## [enforcement-gates] VERIFY.md not auto-created by pipeline — builders must do it manually

### Pattern
The pipeline has no mechanism to automatically create VERIFY.md after a verify command succeeds. Builders must write it manually; the feedback file on gate failure did not explain this.

### Rule
MUST add a builder convention or transition_action that produces VERIFY.md after the verify command passes. Until then, document the manual step explicitly in CONVERSATION_PROMPTS.md.

### Source
Feature: enforcement-gates | Stage: building | Date: 2026-05-25

---

## [adapter-parity] Acceptance criteria that depend on CLI behavior fail silently when CLI is broken

### Pattern
An acceptance criterion was written assuming `pathly-setup --dry-run --host copilot` would list skills in the manifest. In reality `setup_command.py` skips all 20+ skills with a warning for the entire adapter ecosystem — the CLI has never worked for this case. The criterion passed file-creation checks but failed at test time, requiring a rewrite.

### Rule
MUST run the exact CLI command in the acceptance criterion during planning and confirm it produces the expected output before writing it as a criterion. If the command fails, write a criterion that tests what is actually verifiable (file existence, schema shape) rather than CLI output.

### Injection
- Add to `USER_STORIES.md` acceptance criteria review step: "For any criterion that invokes a CLI command, run that command during planning and confirm the output matches expectations. If not, rewrite as a direct file/schema check."

### Source
Feature: adapter-parity | Stage: test | Date: 2026-05-25

---

## [adapter-parity] File path in acceptance criteria must reflect actual codebase structure, not intended structure

### Pattern
The plan specified `src/pathly_data/core/agents/explorer.md` but the file correctly lives at `src/pathly_data/core/agents/research/explorer.md` — following the existing subdirectory structure (research/, planning/, building/, quality/). The acceptance criterion named a non-existent path, failing at test time and requiring a criterion update plus frontmatter addition.

### Rule
MUST glob the target directory and confirm the exact intended path before writing it in an acceptance criterion. For core agents, the path is always `core/agents/<subdirectory>/<name>.md` — always check which subdirectory applies.

### Injection
- Add to `USER_STORIES.md` path criteria: "Before writing any file path in an acceptance criterion, run a glob against the containing directory to confirm the path structure matches the live repo."
- Add to acceptance criteria for new core agent files: include `frontmatter check` as an explicit sub-criterion — `name:` and `description:` fields must be present.

### Source
Feature: adapter-parity | Stage: test | Date: 2026-05-25

---

## [stepper-pathly-ui] CLI arg-forwarding must include an execution verify step, not just a --help check

### Pattern
Conv 1 added `--browser` and `--cdp-port` argparse arguments and verified they appeared in `--help` output. The arguments were parsed correctly but never forwarded to the `run()` function or `launch_browser()`. The CLI silently ignored `--browser electron` at runtime. The tester caught this as AC1.4 failure.

### Rule
MUST include a done-condition that actually exercises the new CLI argument end-to-end — not just confirms `--help` displays it. For any conversation that adds a CLI argument, verify: run the CLI with the argument and confirm it reaches the intended code path (e.g., a log line, a raised error, or a traceable execution branch).

### Injection
- Add to `CONVERSATION_PROMPTS.md` template for CLI-touching conversations: "Done-condition must include a runtime invocation test, not only `--help`. Example: `python stepper/main.py --browser electron --cdp-port 9222 --workflow <file>` — confirm the CDP path is entered."
- Add to `IMPLEMENTATION_PLAN.md` phase for CLI changes: "Verify: run the new flag end-to-end and confirm it reaches the intended dispatch branch — check with a traceable side effect (error message, log line, or unit test mock)."

### Source
Feature: stepper-pathly-ui | Stage: test | Date: 2026-05-31

---

## [stepper-pathly-ui] Studio file touches must include a studio/CLAUDE.md rules audit

### Pattern
Conv 2 added `data-testid` attributes to `HomeScreen.tsx`, `topbar/index.tsx`, and `PanelNav.tsx` correctly, but did not audit the touched files for pre-existing `studio/CLAUDE.md` violations (every `<button>` must have `type=`, no inline styles). The reviewer found 7 violations across those files in the first review cycle, requiring a fix conversation.

### Rule
MUST end every conversation that touches a Studio component file with: "Read studio/CLAUDE.md and confirm all `<button>` elements in touched files have an explicit `type=` attribute, and no new inline styles were introduced."

### Injection
- Add to `CONVERSATION_PROMPTS.md` preamble for Studio-touching conversations: "After making changes, audit all touched files against studio/CLAUDE.md rules: (1) every `<button>` has `type='button'`, (2) no `style={{ }}` props outside the accepted exceptions."
- Add as a standard checklist item in the studio builder conversation template.

### Source
Feature: stepper-pathly-ui | Stage: review | Date: 2026-05-31

---

## [stepper-pathly-ui] Scope adjustments from IMPL_QUESTIONS must propagate to downstream conversation prompts

### Pattern
Conv 2 filed IMPL_QUESTIONS when it discovered that `topbar-panel-plan`, `topbar-panel-editor`, `topbar-panel-settings` had no corresponding DOM buttons. The orchestrator resolved the question and adjusted the spec. However, Conv 5's prompt still referenced `"plan"` and `"editor"` panel navigation in the smoke workflow. The builder produced a workflow with contradictory steps that had to be reverted in review.

### Rule
MUST update all downstream conversation prompts in `CONVERSATION_PROMPTS.md` immediately when a scope adjustment resolves an IMPL_QUESTIONS file. Any prompt that references the now-out-of-scope items must be patched before the next conversation begins.

### Injection
- Add to orchestrator IMPL_QUESTIONS resolution step: "After resolving, grep CONVERSATION_PROMPTS.md for any reference to the out-of-scope item and update the affected conversation prompts before unblocking the next build conversation."

### Source
Feature: stepper-pathly-ui | Stage: building | Date: 2026-05-31

---

## [stepper-pathly-ui] POM locator completeness needs a grep-based done-condition

### Pattern
Conv 3 implemented `TopBarPage` with a `sidebar-nav-settings` locator but omitted `sidebar-nav-monitor`, even though both testids were in `BottomNav.tsx` and both were specified in AC3.3. The tester caught this as FAIL 2. A single grep in the done-condition would have caught it immediately.

### Rule
MUST include a grep-based done-condition for POM locator completeness when a story specifies multiple testids from the same source component. The grep confirms every required testid has a corresponding locator definition in the POM file.

### Injection
- Add to Conv 3 (and any POM-writing conversation) done-condition: "grep -n 'data-testid' poms/pathly/pages/<file>.py — confirm every testid specified in USER_STORIES.md AC has a matching locator definition. List any missing ones before marking done."

### Source
Feature: stepper-pathly-ui | Stage: test | Date: 2026-05-31

---

## [wizard-e2e-flow] Name the feature class explicitly in the planner prompt

### Pattern
The planner agent received a feature description without an explicit class label ("Stepper
automation"). It defaulted to the most common pattern it had seen (Vitest unit-test plan),
requiring manual correction of the plan files before building could start.

### Rule
MUST include one sentence in the planner prompt naming the feature class when it diverges from
the default: "This is a Stepper automation feature, same pattern as stepper-pathly-ui."
One sentence prevents a planning redo.

### Injection
- Add to the planner invocation prompt for Stepper automation features: "Feature class: Stepper
  automation (CDP-driven Playwright over Electron). Pattern: testids first in Studio, then POM
  + glue + workflow in playwright-stepper-framework. Do not generate a Vitest or unit-test plan."

### Source
Feature: wizard-e2e-flow | Stage: planning | Date: 2026-05-31

---

## [wizard-e2e-flow] New features need VERIFY.md pre-created — FSM verify_gate has no "never built" exemption

### Pattern
The FSM verify_gate requires a VERIFY.md with "RESULT: PASS" before transitioning
BUILDING → REVIEWING. For brand-new features with no prior build history, no VERIFY.md
exists. The gate fired twice before a manually pre-created VERIFY.md unblocked the pipeline.

### Rule
MUST add a step to CONVERSATION_PROMPTS.md Conv 1 for any new feature: "After the verify
command passes, write `RESULT: PASS` to `pathly/plans/<feature>/VERIFY.md`." Document this
as a required manual step until the pipeline auto-creates it via a transition_action.

### Injection
- Add to CONVERSATION_PROMPTS.md Conv 1 preamble (all new features): "When the verify
  command passes, write exactly `RESULT: PASS` to `pathly/plans/<feature>/VERIFY.md`.
  This is required to pass the FSM gate into REVIEWING."

### Source
Feature: wizard-e2e-flow | Stage: building | Date: 2026-05-31

---

## [multi-adapter-routing] Fix builder token telemetry before it corrupts multiple features

### Pattern
Four consecutive builder conversations logged `tokens_in: 0, tokens_out: 0, cost_usd: 0.0`. The stop hook fires but builder token data is never captured, making the build stage — the most expensive stage — invisible in cost tracking.

### Rule
MUST verify `src/pathly_hooks/stop_telemetry.py` fires and writes real token counts for builder sessions. Run a single builder conversation and confirm EVENTS.jsonl contains non-zero token fields before starting a multi-conversation feature.

### Source
Feature: multi-adapter-routing | Stage: retro | Date: 2026-06-01

---

## [multi-adapter-routing] Gate feedback must include artifact path + format + example

### Pattern
A `require_artifact` gate fired because a required artifact was missing after the Conv 2 review. The gate feedback did not tell the builder where to write the file, what the first line should be, or what format was expected. A human had to manually unblock the pipeline.

### Rule
MUST include in any `require_artifact` gate `on_fail` feedback: (a) the exact expected path, (b) the required first line or schema shape, and (c) a minimal example content block. Without this, the gate always requires a human unblock.

### Source
Feature: multi-adapter-routing | Stage: building | Date: 2026-06-01

---

## [multi-adapter-routing] Split Studio wizard conversations by typecheck gate

### Pattern
Phases 7-9 touched `utils.ts`, a new component + CSS module, `FlowWizard.tsx`, `draftUtils.ts`, and `types.ts` in a single conversation. This is near the upper bound of reliable single-conversation scope for TypeScript. A TS error introduced in Phase 8 would have required re-running Phase 9 as well.

### Rule
MUST split Studio wizard feature conversations at typecheck boundaries: (a) utility/serializer functions + typecheck; (b) component + wiring + typecheck + visual confirm. Each conversation must end with a passing `tsc --noEmit` before the next begins.

### Source
Feature: multi-adapter-routing | Stage: planning/building | Date: 2026-06-01

---

## [wizard-e2e-flow] Step-count acceptance criteria must be verified against the live component

### Pattern
AC4.2 specified "3 clicks" to advance through the wizard. The builder correctly implemented
4 clicks (matching the actual 5-step wizard at runtime). The acceptance criterion was stale —
written before the wizard step count was finalised, without reading the live component.

### Rule
MUST read the live component source and count interactive steps before writing any acceptance
criterion that contains a step count (wizard steps, nav clicks, form fields, iterations).

### Injection
- Add to USER_STORIES.md planner checklist: "For any criterion that references a step count
  or iteration count, read the live component source and confirm the count before writing it."
- Add to CONVERSATION_PROMPTS.md: "Before accepting the USER_STORIES.md spec, verify any
  step-count criteria against the live component — grep for the step array or render condition."

### Source
Feature: wizard-e2e-flow | Stage: test | Date: 2026-05-31

---

## [antigravity-adapter] Scope gate baseline must be set to a clean post-feature-commit SHA

### Pattern
The scope gate compares `conv_start_sha` (stored in STATE.json) to HEAD. When unrelated commits (e.g., cross-adapter `dispatch_skill.yaml` additions) fall in the same diff window as Conv N work, the scope gate fires spuriously — once per `complete_stage` call, regardless of `resolved_files`. The FSM re-evaluates the git diff live each time and recreates SCOPE_VIOLATION.md.

### Rule
MUST commit Conv N work and update `conv_start_sha` in STATE.json to the resulting HEAD SHA before advancing any scope gate. A scope gate resolution that doesn't include a fresh baseline commit will loop indefinitely.

### Injection
- Add to CONVERSATION_PROMPTS.md Conv N: "After verify passes, commit all changes. Record the commit SHA and update `pathly/plans/<feature>/STATE.json` `conv_start_sha` to this SHA before calling complete_stage."
- Add to FSM gate documentation: "SCOPE_VIOLATION.md is recreated on every complete_stage call if the scope check fails — resolved_files does not suppress re-evaluation."

### Source
Feature: antigravity-adapter | Stage: building | Date: 2026-06-01

---

## [antigravity-adapter] VERIFY.md must be written at Conv N-1 conclusion, not discovered at gate time

### Pattern
The `verify_gate` blocks BUILDING→REVIEWING unless `VERIFY.md` exists with "RESULT: PASS" on line 1. For Conv 4 (the final conversation), VERIFY.md was absent because it was never listed in Conv 3's done-conditions. The gate halted the pipeline and required a manual file creation + pipeline retry.

### Rule
MUST include "Write VERIFY.md with 'RESULT: PASS' as line 1" in the done-conditions of the final implementation conversation, not as a discovered step at gate time.

### Injection
- Add to CONVERSATION_PROMPTS.md final conversation: "After verify command passes, write `RESULT: PASS` to `pathly/plans/<feature>/VERIFY.md`. Include a one-line summary of what was verified (e.g., dry-run output, test counts)."
- Add to plan template: "Phase N (final) done-conditions: [...] + VERIFY.md written with 'RESULT: PASS'."

### Source
Feature: antigravity-adapter | Stage: building | Date: 2026-06-01

---

## [antigravity-adapter] Adapter skill counts drift when new skills added to claude without propagating to other adapters

### Pattern
The antigravity adapter was built targeting 19 claude skills (the count at planning time). By Conv 3, claude had 34 skills. The 15 new skills were never propagated to antigravity. The tester caught the drift, but only because it counted the claude adapter's YAMLs directly — not because the plan had a "stay in sync" criterion.

### Rule
MUST write skill count acceptance criteria as "matching claude adapter's current set" (a relative count, not an absolute number), and include a sync check as an explicit acceptance criterion: "antigravity _meta/ skill YAML count == claude _meta/ skill YAML count."

### Injection
- Add to USER_STORIES.md S3.x (skill YAML stories): "Acceptance criterion: count of antigravity skill YAMLs must equal count of claude skill YAMLs. Run: `diff <(ls src/pathly_data/adapters/claude/_meta/*_skill.yaml | wc -l) <(ls src/pathly_data/adapters/antigravity/_meta/*_skill.yaml | wc -l)`."
- Add to any new adapter plan: "Include a parity check vs claude adapter as a final tester acceptance criterion."

### Source
Feature: antigravity-adapter | Stage: test | Date: 2026-06-01
