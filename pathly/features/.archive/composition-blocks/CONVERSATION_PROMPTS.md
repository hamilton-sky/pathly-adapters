# composition-blocks — Conversation Guide

Split into 4 conversations (Conv 0 pre-flight + 3 build). Each produces a runnable, testable codebase state.
After each conversation, **commit your changes** before starting the next.

> Splitting rule: if a conversation would touch more than one file of the same type, confirm the split is intentional before proceeding. Conv 1 touches two Python files of the same layer — this is intentional (compose.py + composition.yaml are inseparable in this feature).

---

## Conversation 0: Pre-flight baseline (Phase 0)

**Stories delivered:** none (baseline capture only)

**Prompt to paste:**
```
Read pathly/plans/composition-blocks/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

You are running a pre-flight check for the composition-blocks feature. Do NOT write any feature code. This conversation is read-only verification only.

**Steps:**

1. Run `python -m pytest tests/ -q` from the repo root. Record the pass/fail counts and any pre-existing failures.

2. Run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from the repo root. Record any pre-existing type errors.

3. Glob-verify each of these paths exists in the live repo:
   - `src/pathly_data/core/skills/composition.yaml`
   - `src/pathly_orchestrator/compose.py`
   - `src/pathly_orchestrator/state.py`
   - `src/pathly_orchestrator/fsm_ops.py`
   - `tests/test_compose.py`
   - `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`
   - `studio/src/renderer/src/components/FlowWizard/types.ts`
   If any path does not exist, report it — do not attempt to create it.

4. Locate the flow/state validator test file: run glob `tests/test_state*.py`. Record the exact filename(s) found. Conv 2 will need this.

5. Read `src/pathly_orchestrator/state.py` around the allowed-top-level-keys collection and the adapter_map validation block. Record the exact line range where each lives (do not edit).

6. Read `src/pathly_orchestrator/fsm_ops.py` around the `build_prompt` function and the `compose_skill` call site. Record the exact line where `compose_skill` is called and how the active flow yaml is accessed (do not edit).

7. Write all findings to `pathly/plans/composition-blocks/feedback/PREFLIGHT.md`.

Do NOT modify any source file. Do NOT fix pre-existing failures.

After writing PREFLIGHT.md, update pathly/plans/composition-blocks/PROGRESS.md Conv 0 row to DONE.
```

**Expected output:** `pathly/plans/composition-blocks/feedback/PREFLIGHT.md` exists with baseline counts, path confirmations, state.py line ranges, and fsm_ops.py call-site notes.
**Files touched:** `pathly/plans/composition-blocks/feedback/PREFLIGHT.md` (new), `pathly/plans/composition-blocks/PROGRESS.md` (updated)

---

## Conversation 1: Block resolver + composition.yaml (Phases 1–3)

**Stories delivered:** S1, S2, S3

**Prompt to paste:**
```
Read pathly/plans/composition-blocks/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/composition-blocks/feedback/PREFLIGHT.md to see the baseline and confirmed line ranges.

Implement composition-blocks Conversation 1 (Phases 1–3) from pathly/plans/composition-blocks/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_data/core/skills/composition.yaml` — add `blocks:` map (Phase 1)
- `src/pathly_orchestrator/compose.py` — add `resolve_block`, `compose_skill_with_block`, extend `validate_composition` (Phases 2–3)
- `tests/test_compose.py` — add block unit tests (Phase 3)

Do NOT touch `state.py`, `fsm_ops.py`, or any Studio file — those are Conv 2 and Conv 3.

**Scope:**

Phase 1 — `src/pathly_data/core/skills/composition.yaml`:
- Add a top-level `blocks:` map with three entries: `full-build`, `lite-build`, `review-strict`.
- Format: each entry is an ordered list; entries are bare fragment names or `{name: <fragment>, requires: <cap>}` dicts.
- All fragment names must be from the five known fragments: `progress-logging`, `completion-report`, `scout-choreography`, `feedback-protocol`, `spawn-rules`.
- See IMPLEMENTATION_PLAN.md Phase 1 for the exact block definitions.

Phase 2 — `src/pathly_orchestrator/compose.py`:
- Add `resolve_block(block_name, adapter_caps, *, user_blocks=None, manifest=None) -> list[str]`
- Add `compose_skill_with_block(skill, block_name, adapter_caps, *, user_blocks=None, manifest=None) -> str`
- Read IMPLEMENTATION_PLAN.md Phase 2 for full signatures and behavior contracts.
- `adapter_caps=None` must be coerced to `set()` (consistent with existing `_coerce_caps`).
- User blocks take precedence over core blocks by name.
- Unknown block name raises `KeyError` with block name in the message.

Phase 3 — `src/pathly_orchestrator/compose.py` + `tests/test_compose.py`:
- Extend `validate_composition` to check all blocks: fragment existence, known `requires:` capability, no duplicates within a block, no malformed entries.
- If `blocks:` key is absent from manifest, skip block validation (backward-compatible).
- Add the eight block test cases listed in IMPLEMENTATION_PLAN.md Phase 3 to `tests/test_compose.py`.

**Architectural rules:**
- Read the root `CLAUDE.md` and `src/pathly_orchestrator/CLAUDE.md` for project rules before implementing.
- Assembly rule: fragments joined with `\n\n`, each part rstripped — same as existing `compose_skill`.
- No new public API beyond `resolve_block` and `compose_skill_with_block`.
- Do not touch any file outside the three listed above.

**Verify:** `python -m pytest tests/test_compose.py -q`

If verification fails and the fix requires changes outside `compose.py`, `composition.yaml`, or `tests/test_compose.py`, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.

After the verify command passes, write `pathly/plans/composition-blocks/feedback/CONV1_VERIFY.md` with first line `RESULT: PASS` and a one-line summary of what was added.

Update pathly/plans/composition-blocks/PROGRESS.md Conv 1 row and Phases 1–3 to DONE.
```

**Expected output:** `composition.yaml` has a `blocks:` map; `compose.py` exports `resolve_block` and `compose_skill_with_block`; `test_compose.py` has new block tests; all tests pass.
**Files touched:** `composition.yaml`, `compose.py`, `tests/test_compose.py`

---

## Conversation 2: Flow schema + runtime wiring (Phases 4–5)

**Stories delivered:** S4, S5

**Prompt to paste:**
```
Read pathly/plans/composition-blocks/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/composition-blocks/feedback/PREFLIGHT.md for confirmed line ranges in state.py and fsm_ops.py.
Read pathly/plans/composition-blocks/ARCHITECTURE_PROPOSAL.md for the user-block path resolution and capability-gating rules.

Implement composition-blocks Conversation 2 (Phases 4–5) from pathly/plans/composition-blocks/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/state.py` — register and validate `composition:` key (Phase 4)
- `src/pathly_orchestrator/fsm_ops.py` — wire build_prompt to resolve stage block (Phase 5)
- Flow/state validator test file (exact name from PREFLIGHT.md) — add composition key tests (Phase 4)

Do NOT touch `compose.py`, `composition.yaml`, `tests/test_compose.py`, or any Studio file — those are Conv 1 and Conv 3.

**Scope:**

Phase 4 — `src/pathly_orchestrator/state.py`:
- Add `"composition"` to the allowed-top-level-keys collection. Follow the adapter_map precedent EXACTLY (the PREFLIGHT.md records the exact line range).
- Add a validation block for `composition:` after the `adapter_map` validation block:
  - Value must be a dict.
  - Each key must be a declared state in `states:` — unknown state key = validation error.
  - Each value must be a non-empty string — empty string = validation error.
  - Each value must be a resolvable block name — unknown block = validation error.
  - Capability mismatch (block needs `can_spawn`, adapter lacks it) = validation WARNING, not error.
- If `composition:` is absent, skip all above.
- Add tests to the flow/state validator test file: valid flow passes; undeclared state fails; unknown block name fails; no `composition:` key passes.

Phase 5 — `src/pathly_orchestrator/fsm_ops.py`:
- Locate `build_prompt` and the `compose_skill` call site (confirmed line from PREFLIGHT.md).
- Import `compose_skill_with_block` from `compose`.
- When the active flow has a `composition:` key and the current state name is a key in it, call `compose_skill_with_block(agent, block_name, adapter_caps)`.
- When the active flow has no `composition:` key, or no binding for the current state, call `compose_skill(agent, adapter_caps)` unchanged.
- When the named block is missing at runtime, log a warning (include state name + block name) and fall back to `compose_skill` — do not crash the FSM.
- Read ARCHITECTURE_PROPOSAL.md for how `pathlyUserHome` / user blocks path is surfaced to the Python runtime.

**Architectural rules:**
- Read the root `CLAUDE.md` and `src/pathly_orchestrator/CLAUDE.md` before implementing.
- `composition:` is config on an existing state — never a new FSM state or transition.
- Backward-compatibility is non-negotiable: flows with no `composition:` key must behave identically to pre-feature behavior.

**Verify:** `python -m pytest tests/ -q`

If verification fails and the fix requires changes outside the three files listed above, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.

After the verify command passes, write `pathly/plans/composition-blocks/feedback/CONV2_VERIFY.md` with first line `RESULT: PASS` and a one-line summary.

Update pathly/plans/composition-blocks/PROGRESS.md Conv 2 row and Phases 4–5 to DONE.
```

**Expected output:** `state.py` accepts `composition:` key and validates it; `fsm_ops.py` resolves stage blocks; full test suite passes with no regressions.
**Files touched:** `state.py`, `fsm_ops.py`, flow validator test file

---

## Conversation 3: Studio wizard — block authoring + per-stage dropdown (Phases 6–7)

**Stories delivered:** S6, S7

**Prompt to paste:**
```
Read pathly/plans/composition-blocks/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/composition-blocks/ARCHITECTURE_PROPOSAL.md for the user-blocks file format and Studio dependency rules.
Read studio/CLAUDE.md for non-negotiable Studio rules before touching any TypeScript/React file.

Implement composition-blocks Conversation 3 (Phases 6–7) from pathly/plans/composition-blocks/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/FlowWizard/BlockAuthorForm/` — CREATE new subfolder with `index.tsx` + `BlockAuthorForm.module.css` (Phase 6)
- `studio/src/renderer/src/components/FlowWizard/Step4Agents/` — MODIFY to add per-stage block dropdown (Phase 7)
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY to add blockMap state + generateYaml wiring (Phase 7)
- `studio/src/renderer/src/components/FlowWizard/types.ts` — MODIFY to extend wizard types (Phase 7)
- `studio/src/renderer/src/components/FlowWizard/utils/` (generateYaml) — MODIFY to emit `composition:` map (Phase 7)

Do NOT touch `compose.py`, `state.py`, `fsm_ops.py`, `composition.yaml`, or any Python file — those are Conv 1 and Conv 2.

**Scope:**

Phase 6 — CREATE `studio/src/renderer/src/components/FlowWizard/BlockAuthorForm/`:
- Create `index.tsx` + `BlockAuthorForm.module.css` in the new subfolder.
- Component lists the 5 known fragments as selectable items. `spawn-rules` shows "(requires: can_spawn)".
- On submit: validate name is non-empty/non-whitespace; at least one fragment selected.
- Write/merge result into `${pathlyUserHome}/user-blocks.json` as `{ "blocks": { "<name>": [...entries] } }`.
- If block name duplicates a core block name (`full-build`, `lite-build`, `review-strict`), show a visible warning but allow save.
- Studio rules NON-NEGOTIABLE: no inline `style={{}}` — use `.module.css` + tokens.css custom props; one component = one job; 150-line file limit (extract sub-components/hooks/utils if needed); every `<button>` has explicit `type=`; ARIA on all interactive elements.

Phase 7 — MODIFY wizard for per-stage block selection:
- `types.ts`: add `blockMap: Record<string, string>` to wizard state type.
- `utils/generateYaml` (locate exact file by glob): add `blockMap` parameter; emit `composition:` key only when at least one entry in `blockMap` has a non-empty value; omit `composition:` key entirely when all entries are empty.
- `FlowWizard.tsx`: initialize `blockMap` as `{}`; pass to Step4Agents; pass to `generateYaml`; persist to `draftUtils` for autosave.
- `Step4Agents/`: add a `<select>` dropdown per state. Populate options: first option is blank ("none"), then core blocks (`full-build`, `lite-build`, `review-strict`), then any user blocks from `${pathlyUserHome}/user-blocks.json`. If `user-blocks.json` is missing or unreadable, log `console.warn` and show only core blocks.
- Studio rules apply to all modified files.

**Architectural rules:**
- Studio (TypeScript) does NOT import Python. Fragment list is hardcoded to the 5 known names. User blocks are read from `user-blocks.json` on disk.
- `compose.py` is the single source of composition truth at runtime — Studio only writes yaml and the user-blocks file.
- Dependency direction: Studio writes yaml → Python runtime reads and resolves. No cross-language import.

**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (run from repo root)

If verification fails and the fix requires changes outside the files listed above, stop and report.
If fundamentally broken, rollback with `git checkout` on affected files and retry.

After the verify command passes, write `pathly/plans/composition-blocks/feedback/CONV3_VERIFY.md` with first line `RESULT: PASS` and a one-line summary.

Update pathly/plans/composition-blocks/PROGRESS.md Conv 3 row and Phases 6–7 to DONE.
```

**Expected output:** `BlockAuthorForm` component exists and passes typecheck; wizard has a per-stage dropdown; `generateYaml` emits `composition:` map when blocks are selected; TypeScript typecheck clean.
**Files touched:** `BlockAuthorForm/index.tsx` (new), `BlockAuthorForm.module.css` (new), `Step4Agents/` (modified), `FlowWizard.tsx` (modified), `types.ts` (modified), `utils/generateYaml` (modified)
