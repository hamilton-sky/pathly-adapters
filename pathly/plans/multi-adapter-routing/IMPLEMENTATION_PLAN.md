---
name: Implementation Plan
---
# Multi-Adapter Routing — Implementation Plan

## Overview

Add an optional `adapter_map` block to Pathly flow YAML so each stage can be routed to a CLI adapter (claude/codex/copilot). The FSM reads it and emits `preferred_adapter` in `/next_action` (passive — no spawning). A new `pathly-dispatch` skill relays the stage to the chosen adapter. The Studio wizard gains a step to author routing. Backward compatible: flows without `adapter_map` behave exactly as today.

## Layer Architecture

```
Studio Wizard (TS)                FSM (Python)                Coordinator (markdown)
generateYaml emits  ──writes──►   reads adapter_map,   ──►   pathly-dispatch reads
adapter_map block   flow YAML     emits preferred_adapter    preferred_adapter, relays
       ▲                              │                              │
       └── round-trip test ───────────┘   validate_flow_cli is the   │
           (Studio output must pass        single arbiter of shape    ▼
            validate_flow_cli)                                  run in-place OR handoff packet
```

**Dependency direction (invariants):** FSM never imports adapter code (`preferred_adapter` is an opaque string copy, same mechanism as `agent_map`). Coordinator depends on the FSM response contract, never the reverse. Studio produces YAML text only — no runtime FSM coupling.

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** none (verification only)
**Done when:** baseline is green and all assumed anchors confirmed, recorded in the conversation.
**Details:**
- `python -m pytest tests/ -q` passes (record any pre-existing failures as baseline — do not fix here).
- `pathly-fsm-call next-action --flow "team" --topic "<feature>" --project-root "C:/Users/Yafit/pathly-adapters"` succeeds (or start the FSM first).
- Confirm `_response_envelope()` and `_blocked_response()` exist in `src/pathly_orchestrator/fsm_ops.py` and that both build the `/next_action` dict.
- Confirm where `agent_map` is read in `fsm_ops.py` (the pattern `_resolve_adapter` mirrors).
**Verify:** `python -m pytest tests/ -q`

### Phase 1: FSM resolves and emits preferred_adapter   ← Conversation: 1
**File:** `src/pathly_orchestrator/fsm_ops.py` — MODIFY
**Done when:** `/next_action` returns `preferred_adapter`, resolved per the precedence rule, in both the normal and blocked response.
**Delivers stories:** S1
**Depends on:** Phase 0
**Enables:** S4 (dispatch reads this field)
**Details:**
- Add a helper `_resolve_adapter(flow_config, state_name) -> str`:
  - reserve precedence slot 1 for a future per-feature override (leave a commented hook or a no-op branch — do NOT read STATE.json now);
  - return `adapter_map[state_name]` if present;
  - else `adapter_map["default"]` if `adapter_map` present;
  - else `""`.
- Place it beside the existing `agent_map` read so both resolvers sit together.
- Call it in `_response_envelope()` and add `"preferred_adapter": <resolved>` to the returned dict.
- Add the same key to `_blocked_response()` (same envelope shape — do not forget the blocked path).
- Do not change any existing key.
**Verify:** `python -m pytest tests/ -q`

### Phase 2: Unit tests for adapter resolution   ← Conversation: 1
**File:** `tests/` (orchestrator test module — glob to find, e.g. `tests/test_fsm_ops*.py`)
**Done when:** tests cover present / absent / default-only / unmatched-state and all pass.
**Delivers stories:** S1
**Depends on:** Phase 1
**Details:** Cases — (a) `adapter_map` with the state listed → mapped value; (b) state not listed → `default`; (c) no `adapter_map` → `""`; (d) blocked response also carries the field.
**Verify:** `python -m pytest tests/ -q`

### Phase 3: Known-adapter set + optional key   ← Conversation: 2
**File:** `src/pathly_orchestrator/state.py` — MODIFY
**Done when:** `adapter_map` is an accepted optional flow key and `_KNOWN_ADAPTERS` is defined once.
**Delivers stories:** S2
**Depends on:** Phase 1 (shared understanding of the shape)
**Details:** Define `_KNOWN_ADAPTERS = {"claude", "codex", "copilot"}` once. Add `"adapter_map"` to `_KNOWN_OPTIONAL_FLOW_KEYS` (lines ~53-58). The set is a name allowlist only — never a capability registry.
**Verify:** `python -m pytest tests/ -q`

### Phase 4: Validate adapter_map shape   ← Conversation: 2
**File:** `src/pathly_orchestrator/state.py` — MODIFY (in `validate_flow_cli`, lines ~85-166)
**Done when:** a well-formed map passes; missing `default`, unknown adapter, or unknown state each fail with a clear message.
**Delivers stories:** S2
**Depends on:** Phase 3
**Enables:** the round-trip guarantee in Phase 7
**Details:** When `adapter_map` is present: require `default`; every value ∈ `_KNOWN_ADAPTERS`; every non-`default` key ∈ the `states` set already gathered in the validator. Reuse the existing `agent_map` validation pattern for messages.
**Verify:** `python -m pytest tests/ -q`

### Phase 5: Canonical shape doc + example flow   ← Conversation: 2
**File:** `src/pathly_data/CLAUDE.md` — MODIFY; `src/pathly_data/core/flows/team.flow.yaml` — MODIFY
**Done when:** `CLAUDE.md` documents the canonical `adapter_map` shape + precedence, and `team.flow.yaml` carries a commented example `adapter_map` block.
**Delivers stories:** S2
**Depends on:** Phase 4
**Details:** Document WHAT the block contains (the `default` key, the known set, the precedence order) — leave formatting/prose to the author. The `team.flow.yaml` example sits as a sibling to `agent_map`/`role_map`.
**Verify:** `python scripts/check_version_sync.py` (or the validator CLI on `team.flow.yaml`)

### Phase 6: Validator round-trip test   ← Conversation: 2
**File:** `tests/` (flow-validation test module — glob to find)
**Done when:** a fixture flow containing `adapter_map` passes the validator; a fixture with a bad adapter value fails.
**Delivers stories:** S2
**Depends on:** Phase 4
**Verify:** `python -m pytest tests/ -q`

### Phase 7: generateYaml emits adapter_map   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/utils.ts` — MODIFY
**Done when:** `generateYaml()` accepts `adapterMap` and emits the canonical block (default first, then overrides) only when non-trivial.
**Delivers stories:** S3
**Depends on:** Phase 5 (canonical shape is fixed)
**Details:** Add an `adapterMap: Record<string,string>` parameter. Emit after the `agent_map` block (after line ~38), mirroring that loop. Emit nothing when `adapterMap` is `{ default: 'claude' }` with no overrides (zero-diff for skippers).
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

### Phase 8: Adapter Routing wizard step   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/Step5AdapterRouting/Step5AdapterRouting.tsx` (NEW) + `.module.css` (NEW)
**Done when:** the step renders a default selector + per-stage override selectors, all styled with existing theme tokens, no inline styles.
**Delivers stories:** S3
**Depends on:** Phase 7
**Details:** Mirror `Step4Agents` structure. Native `<select>` per stage (closed set of 3 + "Use default"). Default-row card. Color chip per adapter via `var(--accent)` / `var(--green)` / `var(--yellow)` tokens, `aria-hidden`. Labels with `htmlFor`, visible focus ring, `type="button"` on the reset button. Keep the file under ~150 lines (extract a row sub-component if needed).
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

### Phase 9: Wire step into FlowWizard   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` — MODIFY; `draftUtils.ts` — MODIFY; `types.ts` — MODIFY
**Done when:** the step is reachable, routing flows into `generateYaml`, `TOTAL_STEPS` is 6, and draft resume restores routing.
**Delivers stories:** S3
**Depends on:** Phase 8
**Details:**
- `adapterMap` state init `{ default: 'claude' }`; `updateAdapter(key, value)` (delete key on `''`, set `default` directly).
- Render `<Step5AdapterRouting>` at the new step index after Agents; shift the Quality/Review block down one index.
- `TOTAL_STEPS` 5 → 6.
- Add `adapterMap` to: the `yamlPreview` `generateYaml` call, the draft object, `applyDraft`, `startBlank`, and `WizardDraft` in `draftUtils.ts`.
- New step has no validation gate.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` then launch Studio and confirm the step renders + YAML preview updates.

### Phase 10: pathly-dispatch core skill   ← Conversation: 4
**File:** `src/pathly_data/core/skills/utilities/dispatch.md` (NEW)
**Done when:** the skill defines the deterministic relay: read `preferred_adapter`, compare to current adapter, run-in-place or emit verbatim handoff packet.
**Delivers stories:** S4
**Depends on:** Phase 1 (the field must exist)
**Details:** Follow the format of sibling utility skills (`fsm-call.md`, `verify-state.md`). Decision is `pref == "" or pref == current → run in place; else → handoff packet`. The packet = target adapter + `storage_path` + verbatim `agent_hint.instructions`. No process spawning, no instruction rewriting. State explicitly when the target adapter may not be installed.
**Verify:** file exists and contains the decision logic + verbatim-relay rule.

### Phase 11: dispatch_skill.yaml for all three adapters   ← Conversation: 4
**File:** `src/pathly_data/adapters/claude/_meta/dispatch_skill.yaml`, `.../codex/_meta/dispatch_skill.yaml`, `.../copilot/_meta/dispatch_skill.yaml` (3 NEW)
**Done when:** all three meta files exist (mirroring `verify-state_skill.yaml`: `skill`, `filename`, `natural_language`) and `pathly-setup claude --apply` installs the skill without error.
**Delivers stories:** S4
**Depends on:** Phase 10
**Details:** Adapter sync rule — all three must be added together. `filename: pathly-dispatch/SKILL.md`; `natural_language: "/pathly dispatch, dispatch stage, route adapter, dispatch"`.
**Verify:** `pathly-setup claude --apply` succeeds and `~/.claude/skills/pathly-dispatch/SKILL.md` exists.

---

## Prerequisites
- FSM server reachable on `127.0.0.1:8765` (Phase 0 checks this).
- Node deps installed for Studio typecheck (`node_modules/.bin/tsc`).

## Key Decisions
- **Closed adapter set `{claude, codex, copilot}`, validated at flow-author time.** A typo (`codexx`) otherwise routes to nothing and fails downstream where it's hard to trace. Defined once in `state.py`.
- **`default` is required when `adapter_map` is present.** No guessing; an empty/defaultless map is a config error.
- **Validator is the single arbiter of YAML shape; a round-trip test forces Studio to conform.** Prevents TS/Python drift.
- **Passive relay, not auto-launch.** The coordinator routes a prompt; it never spawns a process — preserving the FSM-passive symmetry. Auto-launch (optionally local-LLM/Brightsky hosted) is future work.
- **Per-feature override deferred** but precedence slot 1 reserved now, so adding it later is purely additive.
