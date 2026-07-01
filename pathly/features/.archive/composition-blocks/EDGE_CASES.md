# composition-blocks — Edge Cases

## Category 1: Missing or unknown block reference

### EC-1.1: Flow references a block name that does not exist in the library

- **Trigger:** A flow yaml's `composition:` key names a block (e.g., `"custom-preset"`) that is not in core blocks and not in `user-blocks.json`, at flow load time.
- **Current behavior:** N/A (feature does not exist yet).
- **Expected behavior:** `state.py` validation fails with an error message naming the unknown block name and the state it was bound to. The FSM does not start.
- **Handled in:** Phase 4, Conv 2

### EC-1.2: Block is missing at runtime despite passing load-time validation

- **Trigger:** A user-authored block is referenced at load time (validation passes), but `user-blocks.json` is deleted or corrupted before `build_prompt` runs.
- **Current behavior:** N/A.
- **Expected behavior:** `build_prompt` logs a warning with the state name and block name, then falls back to `compose_skill` (default fragment list). FSM does not crash.
- **Handled in:** Phase 5, Conv 2

### EC-1.3: Block name is an empty string in flow yaml

- **Trigger:** `composition: { BUILDING: "" }` in the flow yaml.
- **Current behavior:** N/A.
- **Expected behavior:** `state.py` validation fails with an error — empty string is not a valid block name.
- **Handled in:** Phase 4, Conv 2

---

## Category 2: Capability gating mismatches

### EC-2.1: Flow binds a fully-gated block to an adapter that lacks the required capability

- **Trigger:** `full-build` block has `spawn-rules` gated behind `can_spawn`. The flow's resolved adapter for BUILDING is `codex`, which lacks `can_spawn`.
- **Current behavior:** N/A.
- **Expected behavior:** At load-time validation, `state.py` emits a WARNING (not an error) noting the capability mismatch. At runtime, `resolve_block` silently drops the gated fragment (`spawn-rules`); the remaining fragments (`completion-report`, `scout-choreography`, `feedback-protocol`) compose normally.
- **Handled in:** Phase 4 (warning), Phase 5 (graceful drop), Conv 2

### EC-2.2: All fragments in a block are gated, and adapter lacks the capability

- **Trigger:** A user-authored block contains only `{name: spawn-rules, requires: can_spawn}`, and the adapter lacks `can_spawn`.
- **Expected behavior:** `resolve_block` returns an empty fragment list. The skill body is still composed (skill header/body only, no extra fragments). No crash.
- **Handled in:** Phase 2 (resolver behavior), Conv 1

---

## Category 3: User block authoring edge cases

### EC-3.1: User names a block the same as a core block

- **Trigger:** User creates a block named `full-build` in the Studio form.
- **Expected behavior:** The form shows a warning ("this name overrides a core block") but allows save. At runtime, the user block takes precedence over the core block of the same name.
- **Handled in:** Phase 6, Conv 3

### EC-3.2: `user-blocks.json` is malformed

- **Trigger:** The file at `${pathlyUserHome}/user-blocks.json` contains invalid JSON (truncated, encoding error, etc.).
- **Expected behavior (Studio):** The FlowWizard dropdown reads the file, catches a parse error, logs `console.warn`, and falls back to showing only core blocks. Wizard does not throw or crash.
- **Expected behavior (runtime):** `compose.py` resolver similarly catches the parse error, logs a warning, and uses only core blocks. FSM does not crash.
- **Handled in:** Phase 5 (runtime), Phase 7 (Studio), Conv 2 + Conv 3

### EC-3.3: User block references an unknown fragment name

- **Trigger:** User-authored block in `user-blocks.json` references `"my-custom-fragment"` which does not exist under `core/skills/fragments/`.
- **Expected behavior:** At flow load-time validation in `state.py`, block validation detects the unknown fragment and fails with an error naming the fragment and the block.
- **Handled in:** Phase 4 (validation extends to user blocks), Conv 2

---

## Category 4: Manifest and composition.yaml edge cases

### EC-4.1: `blocks:` key absent from composition.yaml

- **Trigger:** The manifest has no `blocks:` key (old installs, pre-feature manifests).
- **Expected behavior:** `validate_composition()` skips block validation and returns no errors. All existing skill resolution is unaffected.
- **Handled in:** Phase 3, Conv 1

### EC-4.2: A block entry is neither a string nor a valid `{name, requires}` dict

- **Trigger:** `blocks: { bad-block: [42] }` — a fragment entry is an integer.
- **Expected behavior:** `validate_composition()` returns an error naming the block and the malformed entry.
- **Handled in:** Phase 3, Conv 1

### EC-4.3: A block lists the same fragment twice

- **Trigger:** `full-build: [scout-choreography, scout-choreography]`.
- **Expected behavior:** `validate_composition()` returns an error naming the block and the duplicate fragment name.
- **Handled in:** Phase 3, Conv 1

---

## Category 5: Backward compatibility

### EC-5.1: Existing flow with no `composition:` key

- **Trigger:** Any pre-feature flow yaml loaded after the feature ships.
- **Expected behavior:** `state.py` validation passes unchanged. `build_prompt` takes the existing code path. No behavioral difference whatsoever.
- **Handled in:** Phases 4 + 5, Conv 2

### EC-5.2: Flow has `composition:` with only some states bound

- **Trigger:** `composition: { BUILDING: full-build }` — REVIEWING and other states are unbound.
- **Expected behavior:** BUILDING uses block injection; all other states fall through to default `compose_skill` behavior.
- **Handled in:** Phase 5, Conv 2

---

## Known Limitations

- User-authored fragments (custom fragment files outside `core/skills/fragments/`) are out of scope for this plan. User blocks can only reference the 5 core fragment names.
- Block ordering is fixed by the block definition — the wizard does not expose drag-to-reorder within a block. That is a future enhancement.
- The Studio `BlockAuthorForm` does not validate that a user block's fragment references are resolvable by the Python runtime — that check happens at flow load time in `state.py`. Studio shows only the 5 known core fragment names to minimize the risk.
