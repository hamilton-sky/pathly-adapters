---
name: Edge Cases
---
# Multi-Adapter Routing — Edge Cases

## Category 1: Config / validation

### EC-1.1: adapter_map present without `default`
- **Trigger**: a flow declares `adapter_map` but omits `default`.
- **Expected behavior**: `validate_flow_cli` fails with a message naming the missing `default`. No guessing.
- **Handled in**: Phase 4 / Conv 2.

### EC-1.2: Unknown adapter name (typo)
- **Trigger**: `adapter_map.BUILDING: codexx`.
- **Expected behavior**: validation fails naming `codexx` as not in `{claude, codex, copilot}`. (Failure-case acceptance criterion for S2.)
- **Handled in**: Phase 4 / Conv 2.

### EC-1.3: Per-state key is not a declared state
- **Trigger**: `adapter_map.BUILDIGN: codex` (misspelled state).
- **Expected behavior**: validation fails naming the unknown state.
- **Handled in**: Phase 4 / Conv 2.

### EC-1.4: Wrong-case adapter name
- **Trigger**: `default: Claude`.
- **Expected behavior**: fails the closed-set check (set is lowercase).
- **Handled in**: Phase 4 / Conv 2.

## Category 2: Cross-adapter handoff

### EC-2.1: Artifact-format drift across adapters
- **Trigger**: BUILDING runs on codex and writes `VERIFY.md` / `REVIEW_FAILURES.md`; the next stage runs on claude and must parse it.
- **Expected behavior**: FSM gates/transitions key only on documented markers (e.g. `pass_marker: "RESULT: PASS"`), not adapter prose, so a structurally-conformant artifact is parsed identically regardless of producer. Artifacts follow `core/templates/`.
- **Handled in**: existing marker-based gates (reinforced, not rebuilt); called out as a risk in ARCHITECTURE_PROPOSAL.md.

### EC-2.2: Target adapter not installed
- **Trigger**: `preferred_adapter = codex` but the user has no codex CLI.
- **Expected behavior**: dispatch still prints the handoff packet and states the target may be unavailable — never fails silently.
- **Handled in**: Phase 10 / Conv 4.

## Category 3: FSM resolution

### EC-3.1: Current state not in adapter_map
- **Trigger**: REVIEWING is unmapped but `default` exists.
- **Expected behavior**: `preferred_adapter` resolves to `default`.
- **Handled in**: Phase 1 / Conv 1.

### EC-3.2: No adapter_map at all (backward compatibility)
- **Trigger**: any existing flow that predates this feature.
- **Expected behavior**: `preferred_adapter = ""`; dispatch runs in place; behavior identical to today.
- **Handled in**: Phase 1 / Conv 1.

### EC-3.3: Older FSM, newer dispatch
- **Trigger**: response has no `preferred_adapter` field.
- **Expected behavior**: dispatch treats a missing field as `""` (run in place).
- **Handled in**: Phase 10 / Conv 4.

## Category 4: Studio wizard

### EC-4.1: User skips the step entirely
- **Trigger**: user clicks through the Adapter Routing step with no changes.
- **Expected behavior**: no `adapter_map` block is emitted; saved YAML is byte-identical to today.
- **Handled in**: Phase 7 / Conv 3.

### EC-4.2: Override set then reset to "Use default"
- **Trigger**: user sets BUILDING → codex, then back to "Use default".
- **Expected behavior**: the `BUILDING` key is removed from the emitted map.
- **Handled in**: Phase 9 / Conv 3 (`updateAdapter` deletes the key on empty value).

## Known Limitations (intentionally out of scope)
- Per-feature `STATE.json` adapter override — deferred (precedence slot reserved).
- Auto-launch of the target CLI — passive relay only; auto-launch (optionally local-LLM/Brightsky hosted) is future work.
- No capability checking — the known set validates names, not whether an adapter can actually perform a given stage.
