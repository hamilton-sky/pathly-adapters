# composition-blocks — Architecture Proposal

## Problem Statement

Pathly flows today have no way to vary fragment composition per FSM state without editing skill files. The `composition.yaml` `skills:` map defines a fixed fragment list per skill family (team/build, development/review, etc.), and every flow using that skill gets the same fragments. Operators want per-flow, per-stage presets — a "named block" that bundles a specific fragment combination — selectable in the Studio Flow Wizard without forking yaml.

## Proposed Solution

Add a `blocks:` map to `composition.yaml` (named, ordered fragment-sets). Flow yaml gains an optional top-level `composition:` key that binds FSM state names to block names. At runtime, `build_prompt` detects the binding and composes with `compose_skill_with_block` instead of `compose_skill`. Studio gains a block authoring form and a per-stage dropdown that generates the `composition:` yaml. The feature is backward-compatible: absent `composition:` = current behavior.

## Layer Breakdown

```
composition.yaml
     │  blocks: { full-build: [...], lite-build: [...], review-strict: [...] }
     ▼
compose.py
     │  resolve_block(block_name, adapter_caps, *, user_blocks=None)
     │  compose_skill_with_block(skill, block_name, adapter_caps, *, user_blocks=None)
     │  validate_composition() — extended to cover blocks:
     ▼
state.py
     │  "composition" registered in allowed-top-level-keys
     │  validates: each key = declared state, each value = resolvable block name
     ▼
fsm_ops.py   build_prompt()
     │  if active_flow.composition.get(current_state): → compose_skill_with_block
     │  else: → compose_skill (unchanged)
     ▼
generated flow.yaml
     │  composition: { BUILDING: full-build, REVIEWING: review-strict }
     ▼
Studio FlowWizard (TypeScript/React — writes yaml, does not import Python)
     │  BlockAuthorForm → writes ${pathlyUserHome}/user-blocks.json
     │  Step4Agents dropdown → updates blockMap state
     │  generateYaml → emits composition: key when blockMap has non-empty entries
```

---

## Key Design Decisions

### Decision 1: User block resolution at runtime — the load-bearing risk

**Options considered:**
- A: User blocks live only in Studio; runtime uses core blocks only. (Breaks the feature — user blocks would never be active at runtime.)
- B: User blocks file path is hardcoded in `compose.py`. (Couples Python to the Studio user home path; fragile across installs.)
- C: User blocks file path is passed in at call time from the FSM context (the active flow yaml or an environment/config value), so `compose.py` remains path-agnostic. (Clean separation.)

**Chosen:** C — path is surfaced through the FSM context.

**Mechanism:** The FSM already loads the flow yaml and has access to environment-level config (e.g., `pathlyUserHome`). `fsm_ops.build_prompt` reads `pathlyUserHome` from the FSM config or environment (builder must verify the exact config key via the PREFLIGHT readings). It calls:

```python
user_blocks_path = os.path.join(pathly_user_home, "user-blocks.json")
user_blocks = _load_user_blocks(user_blocks_path)  # returns {} on missing/malformed
compose_skill_with_block(agent, block_name, adapter_caps, user_blocks=user_blocks)
```

`_load_user_blocks` is a small private helper in `compose.py` (or `fsm_ops.py`) that:
- Returns `{}` if the file does not exist (no user blocks).
- Catches `json.JSONDecodeError` and similar, logs a warning, and returns `{}`.
- Extracts the `"blocks"` key from the parsed json; returns `{}` if missing.

This means `compose.py` is entirely path-agnostic — it receives a `user_blocks` dict, never a path.

**Precedence rule:** User blocks override core blocks by name. If a user block and a core block share the same name, the user block's fragment list is used. Core blocks cannot be deleted (they are in the packaged `composition.yaml`) but they can be shadowed.

**Missing block at runtime:** If `build_prompt` resolves the block name and it is not found in either core or user blocks (this should only occur if the user-blocks file was deleted after validation), `build_prompt` logs a warning (`WARNING: block '{block_name}' not found for state '{state}'; falling back to default composition`) and calls `compose_skill(agent, adapter_caps)` instead. The FSM does not crash or halt.

---

### Decision 2: Type safety at resolve time — three enforcement layers

Block name validity is enforced at three points, in order of when errors are cheapest to catch:

**Layer 1 — Studio author-time (TypeScript):**
- The per-stage dropdown in the wizard is populated only from known blocks (core list hardcoded + user-blocks.json at wizard load time). The user cannot type an arbitrary block name — they must select from the dropdown. This prevents typos in generated yaml.
- The BlockAuthorForm shows only the 5 known core fragment names as selectable items. Users cannot reference a non-existent fragment in a user block.

**Layer 2 — Flow validate time (Python, state.py):**
- `state.py` validates the `composition:` key when a flow yaml is loaded (by the FSM at startup, or via `pathly-setup` if it calls `validate_composition`).
- Unknown block name = hard validation error. Flow does not start.
- Undeclared state key = hard validation error.
- Capability mismatch (block needs `can_spawn`, resolved adapter lacks it) = validation WARNING only. The fragment is dropped at runtime; the flow is allowed to start. Rationale: capability mismatches are often intentional (e.g., authoring a flow meant to be portable across adapters).

**Layer 3 — Build-prompt runtime (Python, fsm_ops.py):**
- Defense-in-depth: even if a block was valid at load time but becomes unavailable (user-blocks file deleted), `build_prompt` catches the missing block and falls back gracefully.

---

### Decision 3: Dependency direction — Studio reads/writes yaml; Python resolves

Studio (TypeScript) never imports Python. The data flow is:

```
Studio writes:
  ${pathlyUserHome}/flows/<name>.flow.yaml   (includes composition: map)
  ${pathlyUserHome}/user-blocks.json          (user-authored blocks)

Python reads:
  flow.yaml via state.py + fsm_ops.py
  user-blocks.json via _load_user_blocks() in fsm_ops.build_prompt
  composition.yaml via compose.load_manifest() (core blocks)
```

The 5 fragment names known to Studio (`progress-logging`, `completion-report`, `scout-choreography`, `feedback-protocol`, `spawn-rules`) are hardcoded in the TypeScript component. They do not need to be fetched from Python at runtime because they are a stable, bounded set defined by the core package. If new fragments are added in the future, the Studio list must also be updated (this is an accepted coupling — it is an explicit maintenance contract, not an implicit one).

---

### Decision 4: `composition:` is config attached to an existing state — not a new FSM state or transition

**Confirmed.** The `composition:` key in a flow yaml is purely a content-injection directive. It tells `build_prompt` which fragment preset to use when composing a prompt for that state. It does NOT:
- Create any new FSM state.
- Affect transition logic.
- Change when a state is entered or exited.
- Add any new phase to the pipeline enum.

The FSM topology is unchanged. A flow with `composition: { BUILDING: full-build }` has the same states and transitions as a flow without it; only the content of the composed prompt differs when BUILDING is active.

---

## Key Components

| Component | Location | Description |
|---|---|---|
| `resolve_block` | `compose.py` | Resolves a block name to an ordered list of fragment body strings, applying capability gating |
| `compose_skill_with_block` | `compose.py` | Composes a skill with a named block's fragment list (same assembly rules as `compose_skill`) |
| `_load_user_blocks` | `compose.py` or `fsm_ops.py` | Loads user-blocks.json; returns `{}` on any error |
| `validate_composition` (extended) | `compose.py` | Existing function extended to also validate the `blocks:` map |
| `composition:` key validator | `state.py` | Validates the new optional top-level key following `adapter_map` precedent |
| `BlockAuthorForm` | `studio/.../FlowWizard/BlockAuthorForm/index.tsx` | React component: author + save named user blocks |
| Per-stage block dropdown | `studio/.../FlowWizard/Step4Agents/` (modified) | `<select>` dropdown per state populated from core + user blocks |
| `generateYaml` (extended) | `studio/.../FlowWizard/utils/` | Extended to accept `blockMap` and emit `composition:` key |

---

## Interface Design

**Python public API additions (compose.py):**

```python
def resolve_block(
    block_name: str,
    adapter_caps: set[str] | None,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> list[str]:
    """Return ordered list of resolved fragment body strings for the named block.
    Raises KeyError if block_name is not found in merged library.
    adapter_caps=None treated as empty set.
    user_blocks dict overrides core blocks by name.
    """

def compose_skill_with_block(
    skill: str,
    block_name: str,
    adapter_caps: set[str] | None,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> str:
    """Compose skill body with the named block's fragment list.
    Assembly: skill_body.rstrip() + '\n\n' + '\n\n'.join(frag.rstrip() for frag in fragments).
    """
```

**user-blocks.json schema:**

```json
{
  "blocks": {
    "<block-name>": ["<fragment-name>", {"name": "<fragment-name>", "requires": "can_spawn"}]
  }
}
```

Each value in `"blocks"` follows the same mixed format as `composition.yaml` `skills:` entries.

**generateYaml TypeScript signature addition:**

```typescript
function generateYaml(
  flowName: string,
  storagePath: string,
  validStates: string[],
  agentMap: Record<string, string>,
  transitions: ...,
  gates: ...,
  feedbackRoutes: ...,
  transitionRules: ...,
  adapterMap: Record<string, string>,
  blockMap: Record<string, string>,   // NEW: state → block name; empty string = no binding
): string
```

`composition:` key is emitted only when at least one entry in `blockMap` has a non-empty string value.

---

## Risks

- **User-blocks file deleted after flow validation:** Mitigated by `build_prompt` graceful fallback (Decision 1). Runtime never crashes on a missing block.
- **Fragment list divergence between Studio and core:** Studio hardcodes the 5 known fragment names. If a new fragment is added to `core/skills/fragments/`, the Studio dropdown will not show it until the hardcoded list is updated. This is an explicit maintenance contract — a future `CANDIDATE` lesson or planned enhancement should surface this if the fragment set grows.
- **user-blocks.json grows unbounded:** No pruning mechanism in this plan. If users author many blocks, the file grows. This is acceptable for v1; a block management view is a future enhancement.
- **state.py `_KNOWN_ADAPTERS` frozenset does not include `antigravity`:** The scout confirmed `state.py` has its own `_KNOWN_ADAPTERS` that differs from `compose.py`'s. The `composition:` validator in `state.py` should resolve adapter capabilities via the same mechanism `adapter_map` validation uses — builder must verify this before Phase 4. If `antigravity` is not in `state.py`'s adapter set, the builder should note it and not silently exclude it from capability-gap warnings.
