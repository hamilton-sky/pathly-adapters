# fsm-fan-out — implementation plan

Design: [SPEC.md](SPEC.md). Read it first; this file is the build order.

**Goal of this pass: land Phases A, B and C. STOP before Phase D.**

A/B/C are the *foundation*: they move the fan-out machinery inside the FSM and leave
behaviour **byte-identical** — still one task at a time. Phase D is the single line that
turns concurrency on, and it needs measurement and a real run behind it. Do not do D in the
same pass as C; the whole point of this ordering is that the architecture converges before
any behaviour changes, so if something breaks you know which of the two caused it.

```
  A ─► B ─► C          ← THIS PASS. Architecture converges. Behaviour unchanged.
            │
            ╎  ← STOP HERE
            │
            D ─► E     ← later, with proof
```

---

## Hard constraints — read before touching anything

These will bite a fresh session in exactly this order.

**1. `orchestrator.py` and `scheduler.py` are FROZEN by the size ratchet.**

```
  scripts/file_size_baseline.txt
    supervisor/orchestrator.py : 427   ← may only SHRINK
    supervisor/scheduler.py    : 433   (currently 425)
    supervisor/goal_executor.py: 561   ← may only SHRINK
```

`scripts/check_file_size.py` fails CI if a baselined file grows by even one line — an added
import counts. So **Phase C must make `orchestrator.py` smaller, not bigger**: extract the
stage-spawn block into the new module and call it. This is the same move convergence Phase 1
made on `scheduler.py` (433 → 415 lines *while gaining* per-task retry) and `cost_cap.py`
made by wrapping `spawn_fn` instead of editing the scheduler.

`fsm_compose.py` (359) and `fsm/state.py` (266) are NOT baselined — they have headroom to 400.

**2. Layer rule (`lint-imports`, CI-enforced):** `db → runner → supervisor → http_server`.
New supervisor modules may import `db`/`runner`, never `http_server`.

**3. Tests live in domain folders**, use `tests/_paths.py` anchors, and
`python3 scripts/gen_test_index.py` must be re-run after adding a file.

**4. Golden snapshots.** Phase A changes composed prompt text →
`tests/snapshots/*.claude.md` will drift. Regenerate deliberately (see Phase A) and read the
diff; do not blanket-accept.

---

## Phase A — share the runner-contract constant

**Why first:** it is independently correct, it is the *entire* obstacle the reverted compiled
executor was built to route around, and C cannot be safe without it. Under fan-out, DAG-task
agents run inside an FSM stage — without this block one of them will try to advance the flow
itself and cause a double-advance or a 404 loop.

**The problem.** Two prompt paths, one contract:

```
  fsm_compose.build_prompt        ──► appends "### Runner contract — the supervisor owns
                                       the FSM … never run `pathly-fsm-call` …"
  scheduler.py compose_skill(     ──► appends NOTHING
    "development/execute-task")
```

**Do:**
1. In `fsm_compose.py` (~line 196), lift the `### Runner contract` f-string out of
   `build_prompt`'s `context` into a module-level constant, e.g. `RUNNER_CONTRACT_BLOCK`.
   It interpolates nothing today — verify that before assuming it is a plain constant.
2. Re-export it somewhere both callers can reach without breaking the layer rule.
   `fsm_compose` is a top-level hub module, so `supervisor/scheduler.py` importing from it is
   fine (that direction already exists).
3. In `scheduler.py` (~line 190), append the same constant to the composed task prompt.
   **Watch the ratchet** — `scheduler.py` is baselined at 433 and currently 425, so there are
   8 lines of headroom here. Use them; do not spend them carelessly.

**Test:** `tests/fsm_flows/` — assert both `build_prompt` and the scheduler's composed task
prompt contain the constant, and that it appears exactly once in each (no duplication).

**Verify:**
```bash
python3 -m pytest tests/fsm_flows/ tests/dag_goals/ tests/install_skills/ -q
python3 scripts/check_file_size.py
# snapshots WILL drift — regenerate and READ the diff:
python3 -c "import sys;sys.path.insert(0,'src');from pathly_orchestrator.skills.compose import compose_skill;..."
git diff tests/snapshots/
```

**Done when:** both paths carry the block, snapshots regenerated with a reviewed diff, suites green.

---

## Phase B — the `parallel_states` flow-YAML key (inert)

Pure schema. No engine change, so nothing can regress.

**Do:**
1. Add `parallel_states` to the known-flow-keys list in `fsm/state.py` (the list at ~line 68
   that already holds `feedback_routing`, `feedback_priority`, …).
2. In `validate_flow_dict` (~line 104), validate the shape:
   - keys must be declared states in `flow["states"]` → else an **error**;
   - `max_workers`, when present, must be a positive int → else an **error**;
   - `isolation`, when present, must be one of `lane` | `serial` | `worktree` → else an
     **error**. `worktree` additionally emits a **warning** that `WorktreeIsolation` is still
     a stub.
3. Do NOT add the key to any packaged flow yet. Phase C's tests supply their own flow dicts.

**Shape:**
```yaml
parallel_states:
  BUILDING:
    max_workers: 4        # optional
    isolation: lane       # optional; lane | serial | worktree
```

**Test:** `tests/fsm_flows/test_parallel_states_schema.py` — a valid block passes; an unknown
state name, a zero/negative `max_workers`, and a bad `isolation` each produce an error; a
flow with no `parallel_states` is unchanged.

**Verify:**
```bash
python3 -m pytest tests/fsm_flows/ -q
python3 -c "import sys;sys.path.insert(0,'src');from pathly_orchestrator.fsm.state import validate_flow_dict;import yaml,pathlib
for p in sorted(pathlib.Path('src/pathly_data/core/flows').glob('*.flow.yaml')):
    print(p.name, validate_flow_dict(yaml.safe_load(p.read_text())))"
```

**Done when:** all nine packaged flows still validate clean, and the new key validates.

---

## Phase C — move the fan-out INSIDE the FSM (still serial)

The architectural change. **Behaviour must not change**: use `SerialIsolation`, so a parallel
state still drains one task at a time, exactly as `team-build` does today.

**New module: `supervisor/fan_out.py`** (new file — SOLID rule #2, and the ratchet leaves no
choice).

```python
def parallel_config(flow_config: dict, state_name: str) -> dict | None:
    """The state's parallel_states entry, or None. None => today's single spawn."""

def run_stage(state, flow_config, state_name, instructions, adapter, model,
              run_id, broadcast_fn, *, session, autonomy) -> dict:
    """ONE call site for executing a stage.

    No parallel_states entry -> delegates to _run_stage_via_terminal unchanged.
    Entry present         -> drains the state's ready tasks via scheduler_loop and
                             returns a merged result in the SAME shape the single
                             spawn returns (outcome / error / cost_usd / session_id),
                             so _loop's downstream handling is untouched.
    """
```

**The `orchestrator.py` edit — must be net-negative.** Today `_loop` has the spawn call at
~line 252 (and a second at ~line 295 for the answer-block retry). Extract the surrounding
block into `fan_out.run_stage` and replace both call sites with calls to it. If that does not
come out at or below 427 lines, extract more (the session-continuity block at ~194-230 is a
self-contained candidate) — do not "compress comments" to squeak under.

**Fan-out semantics (serial for now, but write them correctly):**
- Frontier comes from `get_ready_tasks(board, scope, goal_id=state.goal_id)` — the same
  predicate `on_board_count` already uses, so the FSM and the fan-out agree on "ready".
- `isolation = SerialIsolation()` **regardless** of the YAML's `isolation:` value in this
  phase. Log when the config asks for `lane` and the phase pins serial, so it is visible.
- `spawn_fn = _run_stage_via_terminal`, wrapped by `cost_cap.CostCapTracker.wrap` exactly as
  `goal_executor._run_loop` does.
- On drain, merge: `outcome = "failed"` if any task escalated, summed `cost_usd`,
  `session_id = None` (fan-out cannot carry one session across N agents — note it).
- Gates are NOT called here. `_loop` already runs them at the transition, which is the join.

**Test:** `tests/runner_supervisor/test_fan_out.py`, in the style of `test_dag_scheduler.py`
(real `scheduler_loop`, fake `spawn_fn` matching on the task id inside `run_id` — *not* on
prompt substrings; `test_golden_path.py` documents why that flakes):
- a state with no `parallel_states` entry → exactly one `_run_stage_via_terminal` call, with
  the identical arguments as before;
- a parallel state with 3 ready tasks → 3 spawns, and (SerialIsolation) **never two at once**
  — assert on recorded start/end timestamps;
- one task failing → merged `outcome == "failed"`, and `require_tasks_done` blocks the
  transition rather than the stage hard-failing;
- abort mid-drain → no further spawns.

**Verify:**
```bash
python3 -m pytest tests/runner_supervisor/ tests/dag_goals/ tests/fsm_flows/ -q
python3 -m pytest tests/ -q                 # full suite — ~1851 passing today
python3 scripts/check_file_size.py          # orchestrator.py must have SHRUNK
lint-imports && python3 -m mypy src/ && python3 -m black --check src/ tests/
python3 scripts/gen_test_index.py
```

**Done when:** `orchestrator.py` is smaller than 427, the full suite is green, and no
packaged flow declares `parallel_states` — so production behaviour is provably unchanged.

---

## ⛔ STOP HERE

Everything below needs Phase C proven by a real run first.

### Phase D — turn parallelism on (NOT this pass)

One line: `LaneIsolation()` instead of `SerialIsolation()`, honouring `max_workers`. Then add
`parallel_states: {BUILDING: {...}}` to **one** flow and measure.

**Do not start D until:**
- Phase C has completed a real (non-test) run end to end;
- tasks in the target flow declare accurate file footprints — `file_claims.py` only protects
  against collisions it can see, and an undeclared write can clobber a sibling. This is the
  real risk, not a theoretical one;
- the cost-cap overshoot is accepted: `cost_cap` stops *scheduling* past the cap but cannot
  preempt in-flight work, so with N workers the overshoot is up to N tasks, not 1.

### Phase E — retire the second engine (NOT this pass)

`goal_executor._run_loop` becomes a thin alias, then is deleted; `executor: loop` means "run
the flow whose BUILDING is parallel". Only after D is proven. `goal_executor.py` is baselined
at 561 — E only removes code, so the ratchet is satisfied by construction.

---

## Session-start checklist

```bash
git log --oneline -5                        # expect the fan-out docs commit at/near HEAD
cat pathly/features/fsm-fan-out/SPEC.md     # the design
python3 -m pytest tests/ -q                 # baseline: ~1851 passed, 14 skipped
python3 scripts/check_file_size.py          # baseline: 22 known over 400, none new
```

Then start at Phase A. One commit per phase, each with the full gate run in its message.
