# composition-blocks — Implementation Plan

## Overview

This plan adds named, reusable composition blocks to the Pathly framework. A block is a top-level named entry in `composition.yaml` that holds an ordered list of skill fragments. Flow yaml files optionally declare a `composition:` map binding FSM states to block names. At runtime `build_prompt` resolves the active state's block and threads its fragments into the composed prompt. Studio gains a block authoring form and a per-stage dropdown that emits the `composition:` map into generated yaml. The feature is fully backward-compatible: flows with no `composition:` key behave exactly as before.

## Layer Architecture

```
composition.yaml  (blocks: map)
        │
        ▼
compose.py        resolve_block() + compose_skill_with_block()
        │
        ▼
state.py          validate composition: key against declared states + block library
        │
        ▼
fsm_ops.py        build_prompt() → resolves stage block if flow declares one
        │
        ▼
Studio FlowWizard  BlockAuthorForm (author/save) + Step4Agents dropdown (select per state)
        │
        ▼
generated flow.yaml  → composition: { STATE: block-name, ... }
```

---

## Phase 0: Pre-flight baseline   ← Conversation 0 (read-only)

**File:** (no file edits — read-only checks)
**Done when:** Baseline test results are recorded and the studio typecheck result is known, before any feature code is written.
**Delivers stories:** none (pre-flight only)
**Depends on:** nothing
**Enables:** Convs 1-3 (gates: if baseline is already red, note the pre-existing failures so builders don't conflate them with feature regressions)

**Details:**
1. Run `python -m pytest tests/ -q` and record the pass/fail counts and any pre-existing failures.
2. Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from repo root and record any pre-existing type errors.
3. Glob-verify every codebase touchpoint listed in FEATURE_INDEX.md exists:
   - `src/pathly_data/core/skills/composition.yaml`
   - `src/pathly_orchestrator/compose.py`
   - `src/pathly_orchestrator/state.py`
   - `src/pathly_orchestrator/fsm_ops.py`
   - `tests/test_compose.py`
   - `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`
   - `studio/src/renderer/src/components/FlowWizard/types.ts`
4. Locate the flow/state validator test file via `glob tests/test_state*.py` — note the exact filename for Conv 2.
5. Record results in `pathly/plans/composition-blocks/feedback/PREFLIGHT.md`.

**Verify:** `python -m pytest tests/ -q` (record counts; do not fix pre-existing failures)

---

## Phase 1: Default blocks in composition.yaml   ← Conversation 1

**File:** `src/pathly_data/core/skills/composition.yaml` — MODIFY: add top-level `blocks:` map
**Done when:** The file contains a `blocks:` key with `full-build`, `lite-build`, and `review-strict` entries, and `validate_composition()` returns no errors.
**Delivers stories:** S1
**Depends on:** Phase 0 (baseline recorded)
**Enables:** Phase 2 (resolver needs the block definitions)

**Details:**
Add a `blocks:` map at the top level of `composition.yaml` (after `skills:`). Three required entries:

```yaml
blocks:
  full-build:
    - completion-report
    - scout-choreography
    - feedback-protocol
    - {name: spawn-rules, requires: can_spawn}
  lite-build:
    - scout-choreography
  review-strict:
    - scout-choreography
    - {name: spawn-rules, requires: can_spawn}
```

Each entry follows the same mixed format already used in `skills:` entries: bare string or `{name: <fragment>, requires: <cap>}`. All five fragment names under `core/skills/fragments/` are valid: `progress-logging`, `completion-report`, `scout-choreography`, `feedback-protocol`, `spawn-rules`.

**Verify:** `python -m pytest tests/test_compose.py -q` (after Phase 3 adds block tests; at this phase, manual `validate_composition()` invocation suffices)

---

## Phase 2: Block resolver in compose.py   ← Conversation 1

**File:** `src/pathly_orchestrator/compose.py` — MODIFY: add block resolution functions
**Done when:** `compose_skill_with_block("team/build", "full-build", {"can_spawn"})` returns a non-empty string and `compose_skill_with_block("team/build", "unknown-block", set())` raises with "unknown-block" in the message.
**Delivers stories:** S2
**Depends on:** Phase 1 (blocks defined in manifest)
**Enables:** Phase 5 (fsm_ops wires to this)

**Details:**

Add the following to `compose.py`:

`resolve_block(block_name, adapter_caps, *, user_blocks=None, manifest=None) -> list[str]`
- Loads manifest (or uses passed manifest).
- Merges `manifest["blocks"]` with `user_blocks` dict, user blocks taking precedence by name.
- Looks up `block_name`; raises `KeyError` with block name in message if not found.
- Applies `_entry_parts` / `_coerce_caps` gating logic to each entry, identical to how `skills:` entries are processed in the existing `compose_skill`.
- Returns the ordered list of resolved fragment body strings.

`compose_skill_with_block(skill, block_name, adapter_caps, *, user_blocks=None, manifest=None) -> str`
- Calls `_read_skill_body(skill)` for the skill header/body.
- Calls `resolve_block(block_name, adapter_caps, user_blocks=user_blocks, manifest=manifest)` for fragment list.
- Joins with `\n\n` identically to existing `compose_skill` assembly (each part rstripped).
- Returns the composed string.

Public API surface: `compose_skill_with_block` and `resolve_block` are the two new public names. No other public API changes.

`adapter_caps=None` is coerced to `set()` at the top of both functions (consistent with `_coerce_caps` behavior).

**Verify:** `python -m pytest tests/test_compose.py -q`

---

## Phase 3: Block validation in validate_composition   ← Conversation 1

**File:** `src/pathly_orchestrator/compose.py` — MODIFY: extend `validate_composition` to cover `blocks:`
**Done when:** `validate_composition()` on a manifest with a misspelled fragment in a block returns an error, and running it on the valid updated `composition.yaml` returns no errors.
**Delivers stories:** S3
**Depends on:** Phase 2 (resolver exists; validation reuses fragment-existence checks)
**Enables:** Phase 4 (state.py validator can trust block library is valid)

**Details:**

Extend `validate_composition(manifest=None)` (currently validates `skills:` entries):
- If `manifest["blocks"]` key is absent, skip block validation (backward-compatible).
- For each block in `blocks:`:
  - For each entry, apply same existence check as skills: call `_skill_exists` (or equivalent fragment-existence check) on each fragment name.
  - Check `requires:` value is in `_KNOWN_CAPABILITIES` if present.
  - Detect duplicate fragment names within a single block (same fragment listed twice in same block list).
  - Detect malformed entries (not string and not dict with `name` key).
- Accumulate errors with block name context; return/raise consistent with how existing skill validation errors are reported.

Add block tests to `tests/test_compose.py` alongside existing tests:
- Test: valid default blocks pass validation.
- Test: block referencing unknown fragment fails validation with fragment name in error.
- Test: block with unknown `requires:` value fails validation.
- Test: block with duplicate fragment fails validation.
- Test: manifest with no `blocks:` key passes validation.
- Test: `compose_skill_with_block` with gated fragment and empty caps drops the gated fragment.
- Test: `compose_skill_with_block` with unknown block name raises `KeyError`.
- Test: user block overrides core block of same name.

**Verify:** `python -m pytest tests/test_compose.py -q`

---

## Phase 4: flow yaml `composition:` key in state.py   ← Conversation 2

**File:** `src/pathly_orchestrator/state.py` — MODIFY: register and validate `composition:` key
**Done when:** A flow yaml with `composition: { BUILDING: full-build }` passes `state.py` validation, and a flow with `composition: { FAKE_STATE: full-build }` fails validation with a message naming `FAKE_STATE`.
**Delivers stories:** S4
**Depends on:** Phase 3 (block library validated; Conv 1 complete)
**Enables:** Phase 5 (build_prompt can trust the flow's composition binding is valid)

**Details:**

Follow the `adapter_map` precedent exactly:
1. Add `"composition"` to the allowed-top-level-keys collection (~line 60 in `state.py` — builder must locate the exact collection before editing).
2. Add a validation block for `composition:` (after `adapter_map` validation block, ~lines 147-161):
   - `composition:` value must be a dict.
   - Each key must be a state declared in the flow's `states:` list — unknown state key = validation error.
   - Each value must be a non-empty string (block name) — empty string = validation error.
   - Each value must be a block name resolvable in the merged block library (call `load_manifest()` + merge with any user blocks path if available) — unknown block = validation error.
   - A block requiring `can_spawn` for all its entries while the resolved adapter for that state lacks `can_spawn` is reported as a validation warning (not a hard error); the warning message names the block, the state, and the adapter.
3. If `composition:` key is absent, skip all above (backward-compatible).

Add tests to the flow-validator test file (located by glob in Phase 0):
- Test: flow with no `composition:` key passes unchanged.
- Test: flow with valid `composition:` key passes.
- Test: flow with undeclared state in `composition:` fails.
- Test: flow with unknown block name in `composition:` fails.

**Verify:** `python -m pytest tests/ -q`

---

## Phase 5: Runtime wiring in fsm_ops.build_prompt   ← Conversation 2

**File:** `src/pathly_orchestrator/fsm_ops.py` — MODIFY: resolve stage block in build_prompt
**Done when:** When `build_prompt` is called for a state that has a block binding in the active flow, the returned prompt contains the fragments from the named block; a state with no binding returns the same prompt as pre-feature.
**Delivers stories:** S5
**Depends on:** Phase 4 (flow schema validated)
**Enables:** Conv 3 (Studio generates yaml that this runtime correctly interprets)

**Details:**

In `build_prompt()` (around line 103 where `compose_skill` is called):
1. Load the active flow yaml (already available in the FSM context — builder must verify how the active flow is accessed in `fsm_ops.py` before editing).
2. Check if the flow has a `composition:` key and whether the current state name appears as a key.
3. If yes: call `compose_skill_with_block(agent, block_name, adapter_caps)` (importing from `compose.py`) instead of `compose_skill(agent, adapter_caps)`.
4. If the block name is not found in the merged library at runtime, log a warning (include state name and block name) and fall back to `compose_skill(agent, adapter_caps)` — graceful degradation, no FSM crash.
5. If no `composition:` key or no binding for the current state: call `compose_skill` as before (backward-compatible path).

User blocks path at runtime: the resolver needs to know `pathlyUserHome`. The ARCHITECTURE_PROPOSAL specifies how this path is surfaced to the Python runtime. Builder must read ARCHITECTURE_PROPOSAL before implementing.

**Verify:** `python -m pytest tests/ -q`

---

## Phase 6: Studio BlockAuthorForm component   ← Conversation 3

**File:** `studio/src/renderer/src/components/FlowWizard/BlockAuthorForm/` — CREATE: new subfolder with `index.tsx` + `BlockAuthorForm.module.css`
**Done when:** The component renders all 5 fragments as selectable items (with `spawn-rules` labeled `requires: can_spawn`), validates name and selection, and writes a user-blocks file to `${pathlyUserHome}/` on submit.
**Delivers stories:** S6
**Depends on:** Conv 2 complete (yaml schema defined; studio reads it as reference)
**Enables:** Phase 7 (dropdown reads the same user-blocks file)

**Details:**

Component: `BlockAuthorForm`
- Single responsibility: collect block name + fragment selection; write to user-blocks file.
- Fragment list is hardcoded to the 5 known names (not fetched from Python at runtime — Studio is TS-only, per dependency rule in ARCHITECTURE_PROPOSAL).
- `spawn-rules` shows a "(requires: can_spawn)" annotation.
- On submit: validate name is non-empty/non-whitespace; at least one fragment selected; then write/merge into `${pathlyUserHome}/user-blocks.json` (format: `{ "blocks": { "<name>": [...entries] } }`).
- Duplicate-name warning: if name matches a core block name, show a visible warning ("this name overrides a core block") but allow save.
- Studio rules: `.module.css` for all styles using `tokens.css` custom properties; no inline `style={{}}`. Every `<button>` has `type="button"` or `type="submit"`. ARIA labels on all interactive elements. File stays under 150 lines; extract sub-components if needed.

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (from repo root)

---

## Phase 7: Studio wizard per-stage block dropdown   ← Conversation 3

**File:** `studio/src/renderer/src/components/FlowWizard/Step4Agents/` — MODIFY: add per-stage block dropdown
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY: add block-selection state + generateYaml wiring
**File:** `studio/src/renderer/src/components/FlowWizard/types.ts` — MODIFY: extend wizard types
**File:** `studio/src/renderer/src/components/FlowWizard/utils/` (generateYaml) — MODIFY: extend signature + emit `composition:` map
**Done when:** Selecting a block for BUILDING in the wizard and clicking finish produces a flow yaml with `composition: { BUILDING: full-build }`, and leaving all dropdowns blank produces a yaml with no `composition:` key. TypeScript typecheck passes with no new errors.
**Delivers stories:** S7
**Depends on:** Phase 6 (BlockAuthorForm writes user-blocks file)
**Enables:** End-to-end: authored block → saved yaml → runtime resolve

**Details:**

1. **types.ts:** Add `blockMap: Record<string, string>` to wizard state type (maps state name → block name; empty string = no selection).
2. **generateYaml:** Add `blockMap` parameter. Emit `composition:` key only when at least one state in `blockMap` has a non-empty value. Format: `composition: { STATE: "block-name", ... }`.
3. **FlowWizard.tsx:** Initialize `blockMap` state as `{}`. Pass to Step4Agents (or new sibling step). Pass to `generateYaml`. Persist to `draftUtils` for autosave.
4. **Step4Agents (or sibling step):** Add a `<select>` dropdown per state. Populate options from core blocks (hardcoded: `full-build`, `lite-build`, `review-strict`) plus any user-authored blocks read from `${pathlyUserHome}/user-blocks.json` at wizard load time. First option is blank/empty ("none"). On change, update `blockMap[state] = selectedValue`.
5. If `user-blocks.json` is missing or unreadable, log `console.warn` and show only core blocks — wizard does not throw.
6. Studio rules apply: `.module.css`, no inline `style={{}}`, explicit `type=` on buttons, ARIA labels, 150-line limit per file.

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (from repo root)

---

## Prerequisites

- `python -m pytest tests/ -q` must be runnable (baseline recorded in Phase 0).
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` must be runnable from repo root.
- All five fragment files exist under `src/pathly_data/core/skills/fragments/`: `progress-logging`, `completion-report`, `scout-choreography`, `feedback-protocol`, `spawn-rules`.

## Key Decisions

- **Storage = reference by name.** Flow yaml stores `composition: { STATE: block-name }`. Not inline expansion. Decided before this plan; do not re-litigate.
- **User blocks precedence.** User-authored blocks with the same name as a core block override the core block at resolve time. Core blocks cannot be deleted, only shadowed.
- **Capability gating at runtime = graceful drop, not crash.** A block needing `can_spawn` for an adapter that lacks it silently drops those fragments; the remaining fragments compose normally. Validation at flow-load time emits a warning, not an error.
- **Validation gating at validate time = warning for capability mismatches, error for unknown block names.** Unknown block = hard error. Capability gap = warning.
- **composition: is config on an existing state, never a new FSM state.** No changes to FSM transitions, phase names, or state topology.
- **Dependency direction.** Studio (TS) does not import Python. It reads user-blocks from a json file on disk and hardcodes the 5 known fragment names. `compose.py` is the single source of composition truth at runtime.
