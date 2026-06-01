---
name: Conversation Guide
---
# Multi-Adapter Routing — Conversation Guide

Split into 4 conversations (max 4). Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

Dependency: 1 → 2 → 3 (critical path); 4 needs only 1.

---

## Conversation 1: FSM emits preferred_adapter (Phases 0-2)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-routing/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Routing Conversation 1 (Phases 0-2) from pathly/plans/multi-adapter-routing/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every file path exists. Read CLAUDE.md and src/pathly_orchestrator/CLAUDE.md for project rules.

Scope:
- Phase 0 (pre-flight): run `python -m pytest tests/ -q` and record any pre-existing failures as baseline (do NOT fix them). Confirm `_response_envelope()` and `_blocked_response()` exist in src/pathly_orchestrator/fsm_ops.py and locate where `agent_map` is read.
- Phase 1: add a helper `_resolve_adapter(flow_config, state_name)` next to the agent_map read. Resolution order: (1) reserve a slot for a future per-feature override — leave a hook/comment but DO NOT read STATE.json; (2) `adapter_map[state_name]`; (3) `adapter_map["default"]`; (4) `""`. Add `"preferred_adapter": <resolved>` to the dict returned by BOTH `_response_envelope()` and `_blocked_response()`. Change no existing key.
- Phase 2: add unit tests in tests/ (glob for the orchestrator test module) covering: state listed in adapter_map → mapped value; state not listed → default; no adapter_map → ""; blocked response carries the field too.

The canonical adapter_map shape and precedence are in FEATURE_INDEX.md — follow them exactly.

Do NOT touch: state.py, the flow YAML files, anything under studio/, or the skills/adapters directories.
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/multi-adapter-routing/PROGRESS.md phases 0-2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `/next_action` (normal and blocked) returns a `preferred_adapter` string; new unit tests pass; no existing field changed.
**Files touched:** `src/pathly_orchestrator/fsm_ops.py`, `tests/`

---

## Conversation 2: Flow validation + canonical doc (Phases 3-6)

**Stories delivered:** S2

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-routing/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Routing Conversation 2 (Phases 3-6) from pathly/plans/multi-adapter-routing/IMPLEMENTATION_PLAN.md. Conversation 1 (FSM emits preferred_adapter) is complete.

Before editing anything: glob/read the live repo to confirm every file path exists. Read src/pathly_data/CLAUDE.md for the adapter sync rule.

Scope:
- Phase 3: in src/pathly_orchestrator/state.py define `_KNOWN_ADAPTERS = {"claude", "codex", "copilot"}` once, and add "adapter_map" to the known optional flow keys set. Treat the set as a name allowlist only — not a capability registry.
- Phase 4: in `validate_flow_cli`, when adapter_map is present, validate: `default` key required; every value is in `_KNOWN_ADAPTERS`; every non-default key is a declared state in `states`. Each failure prints a clear message naming the offending key/value. Mirror the existing agent_map validation pattern.
- Phase 5: document the canonical adapter_map shape (the `default` key, the known set, the resolution precedence) in src/pathly_data/CLAUDE.md, and add a commented example adapter_map block to src/pathly_data/core/flows/team.flow.yaml as a sibling to agent_map/role_map. Specify WHAT content goes in the block; do not over-specify prose formatting.
- Phase 6: add a validation test in tests/ — a fixture flow with a well-formed adapter_map passes; a fixture with an unknown adapter value fails.

Architectural rules: state.py is the single arbiter of the adapter_map shape — Studio (Conv 3) will be forced to conform via a round-trip test, so get the shape right here.

Do NOT touch: fsm_ops.py, anything under studio/, or the skills/adapters directories (other than the one flow YAML named above).
Verify: `python -m pytest tests/ -q`
After done, update pathly/plans/multi-adapter-routing/PROGRESS.md phases 3-6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Validator accepts well-formed adapter_map, rejects missing-default / unknown-adapter / unknown-state with clear messages; canonical shape documented; example block in team.flow.yaml; tests pass.
**Files touched:** `src/pathly_orchestrator/state.py`, `src/pathly_data/CLAUDE.md`, `src/pathly_data/core/flows/team.flow.yaml`, `tests/`

---

## Conversation 3: Studio wizard adapter step (Phases 7-9)

**Stories delivered:** S3

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-routing/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Routing Conversation 3 (Phases 7-9) from pathly/plans/multi-adapter-routing/IMPLEMENTATION_PLAN.md. Conversations 1-2 are complete; the canonical adapter_map shape is fixed in src/pathly_data/CLAUDE.md and enforced by state.py's validator.

Before editing anything: glob/read the live repo to confirm every file path exists. Read studio/CLAUDE.md — UI rules are non-negotiable (NO inline styles, theme tokens only, one component per folder with a paired .module.css, ~150-line component limit, explicit type="button", ARIA on interactive elements). Read the existing Step4Agents component — your new step mirrors its structure.

Scope:
- Phase 7: in studio/src/renderer/src/components/FlowWizard/utils.ts, add an `adapterMap: Record<string,string>` parameter to `generateYaml()` and emit an `adapter_map:` block (default first, then per-stage overrides in state order) right after the agent_map block. Emit NOTHING when adapterMap is `{ default: 'claude' }` with no overrides (byte-identical output to today for users who skip).
- Phase 8: create studio/src/renderer/src/components/FlowWizard/Step5AdapterRouting/Step5AdapterRouting.tsx + .module.css. A default-adapter selector (claude/codex/copilot, default claude) in a surface card, then one native <select> per non-terminal state offering "Use default" / claude / codex / copilot. Terminal state shows no selector. Each adapter gets a small color chip using var(--accent)/var(--green)/var(--yellow), marked aria-hidden. Every <select> has a <label htmlFor>; visible focus ring via the focus-ring token; reset-overrides button has type="button". Keep under ~150 lines — extract a row sub-component if needed.
- Phase 9: wire it into FlowWizard.tsx — add `adapterMap` state init `{ default: 'claude' }`, an `updateAdapter(key, value)` handler (set 'default' directly; on '' delete the per-stage key; else set it), render the new step after the Agents step and shift the Quality/Review block down one index, change TOTAL_STEPS from 5 to 6, pass adapterMap into the generateYaml call, and add adapterMap to the draft object + applyDraft + startBlank. Add adapterMap to WizardDraft in draftUtils.ts and any needed type in types.ts. The new step has no validation gate.

Acceptance check to satisfy: a flow saved from the wizard with adapter routing must pass the FSM validator (round-trip). Match the canonical shape exactly.

Do NOT touch: any Python file (fsm_ops.py, state.py), the flow YAML files, or the skills/adapters directories.
Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`, then launch Studio and confirm the new step renders, the per-stage selects work, and the YAML preview shows the adapter_map block live.
After done, update pathly/plans/multi-adapter-routing/PROGRESS.md phases 7-9 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** A new Adapter Routing wizard step; `generateYaml` emits the canonical block; routing persists in drafts; skipping yields today's exact YAML; output passes the validator.
**Files touched:** `studio/src/renderer/src/components/FlowWizard/utils.ts`, `FlowWizard.tsx`, `Step5AdapterRouting/Step5AdapterRouting.tsx`, `Step5AdapterRouting/Step5AdapterRouting.module.css`, `draftUtils.ts`, `types.ts`

---

## Conversation 4: pathly-dispatch coordinator (Phases 10-11)

**Stories delivered:** S4

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-routing/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Routing Conversation 4 (Phases 10-11) from pathly/plans/multi-adapter-routing/IMPLEMENTATION_PLAN.md. Conversation 1 is complete, so `/next_action` already returns `preferred_adapter`.

Before editing anything: glob/read the live repo to confirm every file path exists. Read src/pathly_data/CLAUDE.md (adapter sync rule) and an existing utility skill (src/pathly_data/core/skills/utilities/fsm-call.md and verify-state.md) plus its meta (src/pathly_data/adapters/claude/_meta/verify-state_skill.yaml) to match the format.

Scope:
- Phase 10: create src/pathly_data/core/skills/utilities/dispatch.md. The skill is a DETERMINISTIC relay: read the `/next_action` response, take `preferred_adapter` and the adapter it is currently running in. If `preferred_adapter` is "" or equals the current adapter → run `agent_hint.instructions` in place. Otherwise → emit a handoff packet containing the target adapter name, the feature `storage_path`, and the VERBATIM, UNMODIFIED `agent_hint.instructions`. The skill must never spawn a process and never reword the instructions. If the target adapter may not be installed, state that in the packet rather than failing silently. Treat a missing `preferred_adapter` field (older FSM) as "".
- Phase 11: create dispatch_skill.yaml in all THREE adapter meta dirs (claude, codex, copilot) under src/pathly_data/adapters/<host>/_meta/, mirroring verify-state_skill.yaml. Use `skill: dispatch`, `filename: pathly-dispatch/SKILL.md`, `natural_language: "/pathly dispatch, dispatch stage, route adapter, dispatch"`. All three must be added together (adapter sync rule).

Do NOT touch: fsm_ops.py, state.py, the flow YAML files, or anything under studio/.
Verify: `pathly-setup claude --apply` succeeds and `~/.claude/skills/pathly-dispatch/SKILL.md` exists after apply.
After done, update pathly/plans/multi-adapter-routing/PROGRESS.md phases 10-11 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** A `pathly-dispatch` skill that relays or hands off based on `preferred_adapter`, installed across all three adapters.
**Files touched:** `src/pathly_data/core/skills/utilities/dispatch.md`, `src/pathly_data/adapters/{claude,codex,copilot}/_meta/dispatch_skill.yaml`
