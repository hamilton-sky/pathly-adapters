# Assessment — mcp-fsm-driver + pathly-commands-v2

_Review of the two pending plans and the architecture they produce when both land.
Scope: `pathly/plans/mcp-fsm-driver/` and `pathly/plans/pathly-commands-v2/`._

---

## TL;DR

- **mcp-fsm-driver** is the right move and well-engineered. The central insight —
  turn the flow YAML into an *executable spec run by Python*, not a prompt hint
  read by an LLM — is exactly the rearchitecture this codebase needs. The
  detail work (three-level routing, two-call decide protocol, `build_prompt` vs
  `build_prompt_for_agent`, concurrent-write guard, limits-in-YAML) is unusually
  thorough.
- **pathly-commands-v2** is the smaller, lower-risk follow-on. The split between
  Python CLIs (status/log/ff/back) and LLM skills (fix) is correctly drawn.
  Sequencing it after MCP lands is correct.
- **Real concerns are at the seams**: the "orchestrator as fallback" claim is a
  fiction, the `NEEDS_CONTEXT` loop reintroduces LLM-as-controller, the
  auto-flow `decide` UX is undefined, counter-reset semantics across
  pause/resume are unspecified, and `pathly-ff` bypasses the MCP server it
  depends on.

---

## What the two plans do well

**1. Right axis of the rearchitecture.** Today every transition decision passes
through an LLM reading STATE.json and a YAML *as text*. After mcp-fsm-driver,
routing is a `Path.exists()` call or a regex. The category of "LLM forgot to
check `feedback/`", "LLM hallucinated a state name", "LLM skipped a
transition_action" is eliminated outright.

**2. Three-level routing** (`on_artifact` → `on_content` → `decide`).
Cheapest-first ordering, with the LLM invoked only at L3 and only with a
constrained option set.

**3. The two-call decide protocol**
(`mcp-fsm-driver/IMPLEMENTATION_PLAN.md:231-267`) is the best part of the
design. Returning a `{decide: true, ...}` sentinel and letting the *calling*
LLM (which already has rich context from finishing the stage) choose, the
server avoids credentials, network calls, and a separate model dependency.
`fsm.py` stays LLM-free. Decisions are audited via `DECIDE_ROUTING` events.

**4. `build_prompt` vs `build_prompt_for_agent`**
(`IMPLEMENTATION_PLAN.md:178-211`). Subtle but correct — state names go through
`agent_map`, agent names don't. Catching this design-time avoids a class of
`KeyError` at runtime.

**5. Edge case coverage is genuinely strong.** Concurrent-write detection,
human-feedback special case (no `build_prompt` call), `agent_map` validation at
install time, `project_root` explicit and validated, `importlib.resources` for
package-data loading.

**6. v2's CLI-vs-skill split is principled.** `status/log/back/ff` need zero
LLM reasoning → Python CLIs that work in any terminal. `fix` spawns an agent →
LLM skill. The thin-wrapper pattern (skill calls CLI via Bash) gives surface
portability across hosts.

**7. Sequencing.** v2 explicitly blocks on mcp-fsm-driver being fully done.
Correct: `pathly-ff` and `fix` both depend on `next_action`/`complete_stage`
existing.

---

## Concerns and recommended solutions

### 1. "Orchestrator agent kept as fallback" is a fiction

**Concern.** `ARCHITECTURE_PROPOSAL.md:319` and `EDGE_CASES.md:273-283` retain
`orchestrator.md` "as fallback if MCP server unavailable." But Conv 3 rewrites
every skill (`team.md`, `debug.md`, `explore.md`) to call MCP tools; nothing in
the skill checks whether the server is reachable. If MCP is down the user gets
a raw tool error — not a graceful fall back to spawning the orchestrator agent.
EDGE_CASES.md:210-213 says the LLM should "fall back" but the Conv 3 skill
rewrites don't include that instruction.

**Recommended solution.** Pick one of two paths and document it:

- **Option A (preferred): commit fully to MCP.** Delete `orchestrator.md` and
  `orchestrator.yaml`. Update setup_command.py to fail fast if MCP registration
  fails. Skills assume MCP is available.
- **Option B: real fallback.** Add an availability probe to each skill (a
  small MCP no-op call wrapped in try/except). On failure, skill spawns
  `Agent(subagent_type="orchestrator", ...)` and surfaces a warning to the user
  pointing at `pathly-setup --apply`. Add a CI check that `orchestrator.md`
  changes whenever `fsm.py` changes, otherwise it will rot.

Half-fallback (the current plan) is worse than either — `orchestrator.md`
drifts silently and nobody notices until it's needed.

### 2. `NEEDS_CONTEXT` loop is LLM-as-controller, in the skill

**Concern.** The skill loop in `IMPLEMENTATION_PLAN.md:449-460` tracks
`needs_context_count`, checks limits, calls `scout-path`, feeds the summary
back — all enforced by the LLM reading a markdown skill file. Exactly the
pattern the rest of the plan eliminates. The FSM has no visibility into
within-stage context cycles. EVENTS.jsonl doesn't record the counter so after a
pause/resume the counter starts back at zero, giving a pathological agent
`limits.needs_context_per_stage` extra free cycles every restart.

**Recommended solution.** Two paths, can pick either:

- **Option A: move it into Python.** Add a third MCP tool `request_context(query,
  topic, project_root)` that runs `scout-path` (or its equivalent), increments
  a server-side counter, persists the counter in `STATE.json` or
  EVENTS.jsonl, and returns the summary. Skill loop becomes: "if you need
  context, call this; the server enforces the limit." The skill no longer
  counts.
- **Option B: scope the determinism honestly.** Keep the loop in the skill but
  (a) persist `needs_context_count` to EVENTS.jsonl as a `NEEDS_CONTEXT` event
  per cycle, (b) compute the counter from EVENTS.jsonl on resume so it survives
  pauses, (c) document in `ARCHITECTURE_PROPOSAL.md` that determinism applies
  at stage boundaries, not within stages.

Either way, also specify reset semantics: "counter resets on entry to a new
state via STATE_TRANSITION, and on no other event."

### 3. Auto-flow + decide is undefined

**Concern.** Scenario 3 in CONTEXTUAL_MENU_UX.md shows the human typing
`refactor / architecture / minor`. But the codebase supports `autoFlow = true`
mode (`team.md:43-58`). In auto-flow, the plan doesn't say who answers the
decide. Today every `decide` is treated identically — some are routing
heuristics, some are real policy decisions a human must make.

**Recommended solution.** Add an explicit field to the decide schema:

```yaml
transition_rules:
  REVIEWING:
    decide:
      requires_human: false        # NEW: default false
      context_file: REVIEW_FAILURES.md
      question: "What type of fix does this review require?"
      options:
        refactor:     REFACTOR_STAGE
        architecture: ARCH_REVIEW
        minor:        BUILDING
      default: BUILDING
```

Skill behavior:
- `requires_human: false` + auto-flow → calling LLM picks from options based on
  context; skill calls `complete_stage(decision=...)` automatically.
- `requires_human: false` + manual → render Panel A, prompt user, LLM may
  pre-fill suggestion.
- `requires_human: true` → render Panel A and halt regardless of mode, wait
  for explicit user input.

Cheap to add now, impossible to retrofit cleanly later.

### 4. `pathly-ff` bypasses the MCP server

**Concern.** `pathly-commands-v2/IMPLEMENTATION_PLAN.md:292-294`: "Import and
call `complete_stage` from `pathly_orchestrator.mcp_server` directly (not via
the MCP protocol — just a regular Python function call)." This creates two
entry points to FSM mutation: MCP tool calls (auditable, governed by the
server) and direct Python calls (bypass everything). If anyone later adds a
write lock, audit hook, rate limit, or telemetry to the MCP wrapper,
`pathly-ff` won't get it.

**Recommended solution.** Refactor the layering before v2 lands:

```
pathly_orchestrator/
  fsm.py            ← pure functions (already planned)
  fsm_runtime.py    ← NEW: stateful orchestration (next_action, complete_stage
                       as plain Python functions, with locking/audit/etc.)
  mcp_server.py     ← thin MCP protocol adapter; delegates to fsm_runtime
```

Both the MCP tool and `pathly-ff` import from `fsm_runtime`. The server
becomes a 30-line wrapper. Any future cross-cutting concern lives in
`fsm_runtime` and both surfaces inherit it for free.

### 5. `pathly-back` and transition_actions divergence

**Concern.** `pathly-back` rolls STATE.json back one state but explicitly does
*not* reverse `git_commit` or `archive_artifacts` (USER_STORIES.md:108). If the
user rolls back PLANNING→BUILDING, the BUILDING→REVIEWING commit is still in
the git log. Next advance produces a second "complete building stage" commit.

**Recommended solution.** Three options, in increasing strength:

- **Minimum:** STATE_ROLLBACK event must record the SHAs of any commits made by
  the prior STATE_TRANSITION's `transition_actions`. Display them on rollback:
  `"Note: rolled back past commit abc1234 — to undo run git revert abc1234."`
- **Better:** Refuse rollback if the prior transition had `git_commit` actions,
  unless `--force` is passed.
- **Best (long-term):** Make `transition_actions` declare a `reverse:` block.
  `git_commit` reverses to `git revert <sha>`. `archive_artifacts` reverses
  to delete the archived files. `pathly-back` runs the reverse. Out of scope
  here, but worth a follow-up plan.

### 6. Concurrent-write guard is honor-system

**Concern.** `mcp_server.py` reads STATE.json before and after
`run_transition_actions` and raises if it changed
(`IMPLEMENTATION_PLAN.md:172-176`). A sub-agent that writes STATE.json
*between* two `complete_stage` calls — while no MCP request is in flight —
goes undetected. EDGE_CASES.md:236 admits this and falls back to "document in
every agent contract that writing STATE.json is forbidden."

**Recommended solution.** Two layers:

- **Now (cheap):** Add an integrity check on every `next_action` /
  `complete_stage` entry — compute a hash of `STATE.json` and append a
  `STATE_INTEGRITY` event with the hash. If two consecutive calls disagree
  about the hash without an intervening `STATE_TRANSITION`, log a
  `STATE_TAMPERED` warning event. Doesn't prevent the write, but creates an
  audit trail.
- **Later (real fix):** Make EVENTS.jsonl the source of truth and project
  STATE.json from it. `recover_state` reads the last `STATE_TRANSITION` event;
  STATE.json becomes a cache. Out of scope for these plans; document as
  deferred work in `ARCHITECTURE_PROPOSAL.md` rather than pretending the
  before/after read covers it.

### 7. `fix` overlaps with team/debug/explore's blocked-state handling

**Concern.** The Conv 3 update of team.md
(`mcp-fsm-driver/IMPLEMENTATION_PLAN.md:443-481`) already handles
`{blocked: true, ...}` — resolve, delete file, re-call. v2 Conv 3 then adds
`fix.md` which does the same thing. Two implementations of the same protocol;
both must update together when the protocol grows.

**Recommended solution.** Make `fix` the single canonical path:

- Extract the blocked-feedback resolution loop from team/debug/explore.
- `fix.md` becomes the implementation.
- `team.md`/`debug.md`/`explore.md` on `blocked: true` call `fix` via a skill
  invocation (or inline the same content via stitch).
- One place to update when feedback handling changes.

### 8. `pathly-ff` "likely_next" preview lies

**Concern.** `pathly-commands-v2/IMPLEMENTATION_PLAN.md:300-303`: "Read flow
YAML to evaluate what the next state would be (L1 check only)." If L1 doesn't
match but L2 or L3 would fire, the preview is wrong and the user proceeds with
incorrect expectations.

**Recommended solution.** Call the actual `evaluate_transition_rules` from
`fsm.py` — it's a pure function, cheap to run twice (once for preview, once
inside `complete_stage`). If it returns a decide sentinel, display the question
in the preview too. If it returns a state name, show it. No new code; just
reuse what's already deterministic.

### 9. Three different "find active topic" implementations

**Concern.** `pathly-status`, `pathly-log`, `pathly-back`, and `pathly-ff` each
auto-detect the active topic with slightly different logic. Behavior will
diverge command-to-command.

**Recommended solution.** Add a shared helper, ship it in Conv 1 of v2 before
any CLI uses it:

```python
# src/pathly_orchestrator/discovery.py
SCAN_ROOTS = {
    "pathly/plans": "team",
    "pathly/debugs": "debug",
    "pathly/explorations": "explore",
}

def find_active_topic(project_root: Path, include_done: bool = False)
        -> tuple[Path, str, str] | None:
    """Return (storage_path, flow_name, topic) for most recently modified
    non-DONE STATE.json, or None if nothing matches."""
    ...

def list_topics(project_root: Path, include_done: bool = False)
        -> list[tuple[Path, str, str, str, int]]:
    """Return (storage_path, flow, topic, current_state, conv) per topic."""
    ...
```

All four CLIs import from here.

### 10. Copilot adapter inconsistency

**Concern.** mcp-fsm-driver Conv 3 only updates Claude and Codex adapters
(`IMPLEMENTATION_PLAN.md:381-388`). pathly-commands-v2 Conv 1-3 adds Copilot
adapters for all new skills. After both plans land: status/log/back/ff/fix
work on Copilot, but team/debug/explore (the actual pipeline entries) don't.

**Recommended solution.** Pick a Copilot stance up front:

- **Option A:** Add Copilot to mcp-fsm-driver Conv 3 — three more `_meta`
  files. Trivial scope addition; keeps the surface consistent.
- **Option B:** Declare Copilot out of scope for the MCP migration. Drop the
  Copilot `_meta` files from v2 Conv 1-3 to match. Document the gap in
  `ARCHITECTURE.md`: "Copilot does not support MCP — only the legacy
  orchestrator path works there, and that path is deprecated."

Either is fine; the current split is the worst of both.

### 11. Flow YAMLs are user-shaped but package-loaded

**Concern.** `importlib.resources` is correct for shipped flows, but it means
users can't supply their own `team.flow.yaml` (e.g., to customize states for a
team-specific pipeline). Today's `state.py:40` uses `load_flow(yaml_path)` with
a file path — that flexibility is being removed.

**Recommended solution.** Search order in the MCP server's flow loader:

```python
def load_flow_resolved(flow_name: str, project_root: Path) -> dict:
    # 1. Project-local override
    local = project_root / "pathly" / "flows" / f"{flow_name}.flow.yaml"
    if local.is_file():
        return yaml.safe_load(local.read_text())
    # 2. Shipped default
    return yaml.safe_load(
        files("pathly_data").joinpath(f"core/flows/{flow_name}.flow.yaml").read_text()
    )
```

`validate_flow_cli` already handles arbitrary paths, so the validation story is
unchanged. If user-custom flows are explicitly out of scope, say so in
`ARCHITECTURE_PROPOSAL.md` rather than silently dropping the capability.

### 12. Counter reset semantics across pause/resume

**Concern.** `needs_context_count` and `feedback_round_count` are "reset at the
start of each stage" but nothing in EVENTS.jsonl records the counter, and the
plan doesn't define when "start of stage" actually fires. Pause/resume cycles
get free cycles.

**Recommended solution.** Record counters as events:

```
{"type": "NEEDS_CONTEXT",      "state": "BUILDING", "count": 1, ...}
{"type": "FEEDBACK_RESOLVED",  "state": "BUILDING", "round": 2, ...}
```

Skill `recover_state` extension: count occurrences since last
`STATE_TRANSITION` for the current state. That gives a stable counter across
pauses without persisting it in STATE.json. Document the reset rule:
"counters reset on entry to a new state via STATE_TRANSITION, and on no other
event."

---

## What the architecture looks like after both plans land

```
┌─────────────────────────────────────────────────────────┐
│ Host LLM (Claude Code / Codex / Copilot)               │
│   reads skill .md, invokes MCP tools or shell CLIs     │
└─────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
┌──────────────────────────────┐   ┌──────────────────────┐
│ Skills (LLM)                 │   │ CLI scripts          │
│   team / debug / explore     │   │   status, log,       │
│   fix, meet, go, pause       │   │   back, ff           │
│   (panel render, NEEDS_CTX,  │   │   (Python entry pts) │
│    feedback loop)            │   │                      │
└──────────────────────────────┘   └──────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│ MCP server: next_action, complete_stage(decision=…)    │
│   (mcp_server.py — protocol adapter + decide protocol  │
│    + prompt building from agent contracts)             │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ FSM core (pure Python, no LLM, no MCP)                 │
│   recover_state · evaluate_transition_rules            │
│   route_feedback · run_transition_actions              │
│   write_state · append_event                           │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Flow YAMLs (executable spec)                            │
│   team.flow.yaml · debug.flow.yaml · explore.flow.yaml │
│   states · transitions · agent_map · feedback_routing  │
│   transition_rules (L1/L2/L3) · transition_actions     │
│   limits                                                │
└─────────────────────────────────────────────────────────┘
```

### What's good about this end state

- **Pure-Python testable core.** `fsm.py` has zero LLM dependencies and zero
  MCP coupling. The full state machine is unit-testable without a server,
  API keys, or an LLM.
- **Two protocol surfaces, one core.** MCP tools for in-conversation use, CLI
  scripts for terminal use, both backed by the same FSM.
- **Flow YAMLs become the contract.** A new flow is a YAML edit + maybe a new
  agent contract. No new code. That's the property a workflow framework wants.
- **Determinism where it matters; LLM where it has to be.** L1 + L2 cover most
  transitions; L3 is the explicit "judgment needed" escape hatch with an audit
  trail.
- **Limits + per-state override.** Pre-empts "agent loops forever" failures,
  with knobs at the level operators expect.

### What's still wobbly after both plans

- **The skill layer still does a lot.** Panel rendering, NEEDS_CONTEXT cycle,
  feedback resolution loop, decide UX, limit enforcement, "find active topic"
  — all in markdown that an LLM must follow correctly. The plan moves FSM
  routing into Python but the meta-loop around the FSM is still LLM-controlled.
- **STATE.json is still mutable from anywhere.** The before/after-read guard is
  the weakest part of the determinism story. EVENTS-as-truth would close it;
  out of scope here, but a known liability.
- **`orchestrator.md` will silently rot** unless explicitly retired or kept in
  sync via CI.
- **Three commands, three topic-discovery paths** until consolidated.

---

## Sequencing recommendation

1. **Land mcp-fsm-driver and let it bake one to two weeks before starting v2.**
   The two-call decide protocol and the MCP-on-Codex story need real-world
   miles. If something breaks, you don't want v2 changes mixed into the diff.
2. **Add `requires_human: bool` to the decide block schema** as part of
   mcp-fsm-driver Conv 1 — cheap now, expensive to retrofit.
3. **Pull `complete_stage`'s logic into `pathly_orchestrator.fsm_runtime`**
   before v2 starts. Both MCP and `pathly-ff` go through it. No CLI bypass.
4. **Pick a stance on the orchestrator fallback** — wire it fully or delete it.
   Don't ship the limbo state.
5. **Add `find_active_topic()` and `list_topics()` helpers** as v2 Conv 1's
   first commit, before any CLI uses them.
6. **Document residual non-determinism honestly** in `ARCHITECTURE_PROPOSAL.md`:
   STATE.json is still writable, NEEDS_CONTEXT loop is LLM-controlled,
   counter-reset semantics across pauses. These aren't fatal — they're the
   line between v1 and v2 of the determinism story, and the doc should say so.

---

## Bottom line

This is a thoughtful, well-decomposed migration. The bones of the new
architecture are right. The places where I'd push back are mostly around
fallback/migration paths, residual LLM-as-controller patterns, and a small
amount of consolidation across the CLIs. None of that is blocking; all of it
is worth resolving before merge.
