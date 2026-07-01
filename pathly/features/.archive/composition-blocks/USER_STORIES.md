# composition-blocks — User Stories

## Context

Today every skill in a Pathly flow pulls from a fixed fragment list defined in `composition.yaml` under the `skills:` map. Operators who want to vary fragment composition per flow stage must fork or hand-edit yaml — there is no first-class concept of a named preset. This plan introduces **composition blocks**: named, ordered fragment-sets that a flow yaml can reference by name per FSM state. Blocks ship as defaults in `composition.yaml`; Studio users can author their own. The net effect is that an operator can choose "full-build" or "lite-build" for the BUILDING stage and "review-strict" for REVIEWING, without touching any skill file.

---

## Stories

### Story S1: Default block library in composition.yaml

**As a** Pathly operator, **I want** a set of default named blocks shipped in `composition.yaml`, **so that** I can reference them immediately in any flow yaml without authoring anything new.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/skills/composition.yaml` contains a top-level `blocks:` map with at least the three blocks: `full-build`, `lite-build`, and `review-strict`.
- [ ] Each block value is an ordered list where each entry is either a bare fragment name or a `{name, requires}` dict, consistent with the existing `skills:` entry format.
- [ ] All fragment names referenced in the default blocks exist under `src/pathly_data/core/skills/fragments/`.
- [ ] `validate_composition()` passes with no errors on the updated `composition.yaml`.

**Edge Cases:**
- A default block references a fragment that does not exist on disk — `validate_composition()` must return an error naming the missing fragment and the block that references it.
- A default block lists the same fragment twice — `validate_composition()` must return an error naming the duplicate and the block.

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Block resolver in compose.py

**As a** Pathly runtime, **I want** `compose.py` to resolve a block name into a composed skill body, **so that** `build_prompt` can request composition-by-block without knowing the fragment list.

**Acceptance Criteria:**
- [ ] A public entry point (e.g. `compose_skill_with_block(skill, block_name, adapter_caps)` or a `block=` kwarg on `compose_skill`) exists in `compose.py`.
- [ ] Calling it with a valid block name and full caps produces the same output as manually expanding that block's fragment list through the existing `_entry_parts` / gating logic.
- [ ] Calling it with a block name that requires `can_spawn` and `adapter_caps=set()` silently drops the gated fragment (consistent with existing per-skill gating behavior).
- [ ] Calling it with an unknown block name raises a `KeyError` or named exception with the block name in the message.
- [ ] The merged block library (core blocks + any user blocks passed in) is used for resolution; user blocks with the same name as core blocks take precedence.

**Edge Cases:**
- Block name is an empty string — raises immediately with a clear message.
- `adapter_caps` is `None` — treated as empty set (no capabilities).

**Delivered by:** Phase 2 → Conversation 1

---

### Story S3: Block validation in validate_composition

**As a** pipeline operator, **I want** `validate_composition()` to check every block in the library, **so that** broken blocks are caught at install time rather than at runtime.

**Acceptance Criteria:**
- [ ] `validate_composition()` iterates all blocks in the `blocks:` map and checks each entry: fragment exists on disk; `requires:` value is a known capability name.
- [ ] A block with an unknown `requires:` value causes `validate_composition()` to return/raise an error identifying the block and the unknown capability.
- [ ] Blocks with no errors do not appear in the validation output.
- [ ] Existing `skills:` validation is unaffected — no regressions.

**Edge Cases:**
- `blocks:` key is absent from the manifest — `validate_composition()` completes without error (backward-compatible).
- A block entry is neither a string nor a `{name, requires}` dict — error identifying the block and the malformed entry.

**Delivered by:** Phase 3 → Conversation 1

---

### Story S4: flow yaml `composition:` key validation

**As a** flow author, **I want** the flow-yaml validator to accept and validate an optional `composition:` key, **so that** invalid block references are caught before a flow is run.

**Acceptance Criteria:**
- [ ] `state.py` registers `composition` as an allowed top-level key in a flow yaml (alongside `adapter_map`).
- [ ] If `composition:` is present, each key must be a state declared in the flow's `states:` list — any undeclared state key causes a validation error.
- [ ] If `composition:` is present, each value must be a block name that exists in the resolved block library (core + user) — an unknown block name causes a validation error.
- [ ] A flow yaml with no `composition:` key passes validation with current behavior unchanged.

**Edge Cases:**
- `composition:` value for a state is an empty string — validation error (blocks must be named).
- A block referenced in `composition:` needs `can_spawn` but the flow's resolved adapter for that state lacks the capability — this is caught and reported as a validation warning (not a hard error; the fragment is gracefully dropped at runtime per the Architecture Proposal).

**Delivered by:** Phase 4 → Conversation 2

---

### Story S5: Runtime block injection in build_prompt

**As a** Pathly FSM runtime, **I want** `build_prompt` to inject a block's fragments when the active flow declares a `composition:` binding for the current stage, **so that** the composed prompt reflects the flow-level preset without changing any skill file.

**Acceptance Criteria:**
- [ ] When a flow has `composition: { BUILDING: full-build }` and FSM enters BUILDING, the assembled prompt uses the `full-build` block's fragment list instead of the skill's default fragment list.
- [ ] When the active flow has no `composition:` key, `build_prompt` behavior is identical to pre-feature behavior.
- [ ] When the active flow's `composition:` key does not include a binding for the current state, `build_prompt` falls back to the skill's default fragment list.
- [ ] If the named block is missing from the resolved library at runtime, `build_prompt` logs the failure and falls back to the skill's default fragment list (graceful degradation — does not crash the FSM).

**Edge Cases:**
- FSM transitions to a state not listed in `composition:` — default behavior (no block injection).
- Block exists but all its gated fragments are dropped for the current adapter — the skill body is still composed (with only the ungated fragments that remain, which may be zero additional fragments).

**Delivered by:** Phase 5 → Conversation 2

---

### Story S6: Studio block authoring form

**As a** Studio user, **I want** a form to author and save named composition blocks, **so that** I can build custom presets without editing yaml files by hand.

**Acceptance Criteria:**
- [ ] A block authoring form component exists under `studio/src/renderer/src/components/FlowWizard/BlockAuthorForm/` with its own `.module.css`.
- [ ] The form lists the 5 known fragments (`progress-logging`, `completion-report`, `scout-choreography`, `feedback-protocol`, `spawn-rules`) as selectable items.
- [ ] `spawn-rules` is displayed with a visible `requires: can_spawn` label.
- [ ] Submitting the form with a name and at least one fragment writes a user-blocks file under `${pathlyUserHome}/` in a documented format (json or yaml, architect's choice per ARCHITECTURE_PROPOSAL).
- [ ] No inline `style={{}}` is used; all styles use `.module.css` tokens. Every `<button>` has an explicit `type=` attribute. Interactive elements have ARIA labels.
- [ ] The component file is under 150 lines; any extracted sub-components each have their own file.

**Edge Cases:**
- Block name is empty or contains only whitespace — form shows a validation error and does not save.
- No fragments are selected — form shows a validation error and does not save.
- A block name duplicates a core block name — form shows a warning but allows save (user block takes precedence at runtime).

**Delivered by:** Phase 6 → Conversation 3

---

### Story S7: Studio wizard per-stage block dropdown

**As a** Studio flow author, **I want** to choose a composition block for each FSM state in the Flow Wizard, **so that** the generated flow yaml includes a `composition:` map without hand-editing.

**Acceptance Criteria:**
- [ ] The Flow Wizard (Step 4 Agents step or a sibling step) shows a block dropdown per state, populated with core blocks and any user-authored blocks from `${pathlyUserHome}/`.
- [ ] Selecting "none" (or leaving blank) for a state emits no `composition:` entry for that state.
- [ ] The generated yaml from `generateYaml` includes a `composition:` map only when at least one state has a block selected; it is omitted entirely when no selections are made.
- [ ] Wizard draft autosave (`draftUtils`) preserves the block selections across page reloads.
- [ ] The TypeScript typecheck command (`node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`, run from repo root) passes with no new errors.

**Edge Cases:**
- User has no saved user blocks — dropdown shows only core blocks; no error.
- `${pathlyUserHome}/` user-blocks file is missing or malformed — dropdown falls back to core blocks only and logs a console warning; wizard does not crash.

**Delivered by:** Phase 7 → Conversation 3
