# STORM_SEED — fsm-friction-fixes

Storm output from the architect. Three independent friction points in the FSM:
auto-start reliability, scope-gate false positives, and implicit multi-conversation
routing.

```
Today's pain                          Goal
─────────────────────                  ─────────────────────────────────
1. "FSM server unavailable"  ──►  Zero-touch start, polled health
2. SCOPE_VIOLATION on noise  ──►  Track touched files, not git diff
3. Reviewer forgets marker   ──►  FSM knows conv count first-class
```

---

## Problem 1 — FSM server auto-start

### Root cause

Auto-start logic already exists in `src/pathly_orchestrator/fsm_http_client.py`
(`_start_server` at line 77, `ensure_server_running` at line 92). It is unreliable
for three concrete reasons:

1. **Skill markdown contradicts the helper.** `src/pathly_data/core/skills/utilities/fsm-call.md`
   lines 28–46 instruct Bash with `python -m pathly_orchestrator.http_server &`.
   On Windows PowerShell `&` is a call operator, not a background marker — the
   command fails silently. On macOS/Linux the `&` works, but stdout/stderr inherit
   the parent shell, so when the skill process ends the OS may signal SIGHUP and
   kill the new server. The packaged `pathly-fsm-call` CLI (which already does
   the right thing via `subprocess.Popen` with DEVNULL) is mentioned only as
   "preferred" — not mandatory — so the failure modes coexist.
2. **Fixed 2 s sleep instead of poll.** `ensure_server_running` (line 96–98)
   sleeps 2 s then makes one health probe. Flask cold-start on Windows can take
   3–6 s when the import graph hasn't been warmed (pyyaml + flask + importlib.resources).
   The single retry then reports the misleading "Start it with: python -m …"
   message — even though the server is mid-boot and will be live a second later.
3. **No PID file or lock.** Two concurrent skills both trigger `_start_server`
   and race on port 8765. The loser's Flask raises `OSError: [WinError 10048]`
   and the orphaned `python.exe` keeps running. There's no detection of "already
   starting" vs "definitely dead".

### Proposed solution

Make `ensure_server_running` the single source of truth, fix its three defects,
and route the skill markdown through it unconditionally.

| File | Change |
|---|---|
| `src/pathly_orchestrator/fsm_http_client.py` | `ensure_server_running`: replace fixed `time.sleep(2)` with a poll loop (`for _ in range(30): if _health_ok(): return; time.sleep(0.25)`) → 7.5 s ceiling, 250 ms granularity. In `_start_server`, on POSIX add `start_new_session=True` so SIGHUP from the parent does not kill the daemon; on Windows add `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS`. Write a PID file to `<user_cache>/pathly/fsm.pid` before spawning; if PID exists and is alive, skip spawn and just poll. |
| `src/pathly_data/core/skills/utilities/fsm-call.md` | Replace Steps 2 and 3 with a single instruction: call `pathly-fsm-call next-action …` (or `complete-stage` / `record-activity`). The helper already does health-check + auto-start + retry. Remove the `python -m … &` fallback entirely — that path is the bug. |
| `src/pathly_orchestrator/http_server.py` | Add a no-op `/health` short-circuit that returns 200 before any logging or rate-limit middleware runs, to keep startup probes fast and unmetered. |

Note: do **not** introduce a new `pathly-fsm-call` flag — keep the existing
contract. The fix is internal to `ensure_server_running` plus removing the
broken fallback from the skill.

### Tradeoffs

- **Cold-start latency on first skill call rises from ~2 s to up to ~7.5 s in
  the worst case.** Acceptable because the alternative today is "skill fails,
  user opens terminal, retries" — that's >30 s wall time.
- **PID file is OS-specific.** On Windows, an orphaned PID from a crashed
  earlier session looks "alive" until you actually probe it. Mitigated by
  always running `_health_ok()` before trusting the PID — health check is the
  real truth, PID file is just a hint to avoid spawn-storm during concurrent
  skills.
- **DETACHED_PROCESS on Windows hides server stderr.** Already true today
  (Popen uses DEVNULL). Acceptable — logs go to the structured logger and the
  user can run `pathly-fsm-http` manually if they want to see them.

### Alternative considered

**Background it from `pathly-setup claude --apply`** — make installation
register a per-user Windows scheduled task / launchd plist / systemd user
service that boots the FSM server on login. Rejected: adds an OS-specific
install surface (3 codepaths × 3 hosts), creates an "always-on" service the
user didn't ask for, and breaks the offline/portable install story.
Lazy-start-on-first-call is the right contract; we just need to make it work.

---

## Problem 2 — Scope gate false positives

### Root cause

`src/pathly_orchestrator/fsm.py:399-406` runs `git diff --name-only <conv_start_sha>`.
That command's semantics: "files whose state differs from `<sha>`, including
working tree". So **any uncommitted change made before the conversation started
is treated as if the builder touched it.** The baseline SHA is stamped in
`fsm_ops.py:349-353` at `next_action` time — but the baseline is HEAD, not the
working-tree state, so anything modified-but-uncommitted is permanently visible
to the gate.

Reading the active state right now:

```json
// pathly/plans/fsm-friction-fixes/STATE.json
{ "conv_start_sha": "ec20661…", "current": "STORMING" }
```

Two files are modified-but-uncommitted at that SHA (`SKILL_EXECUTION.md`,
`test_setup.py` per gitStatus). Those would be flagged as out-of-scope by
the gate the moment the BUILDING→REVIEWING transition is attempted, regardless
of what the builder did.

The exemption list at `fsm.py:424-429` already papers over this for
`pathly/plans/`, `src/pathly_orchestrator/`, and `.tsbuildinfo` files — that
exemption list is itself evidence that the gate's mental model is wrong.

### Proposed solution

Replace "diff against SHA" with "track files the builder actually wrote."

| File | Change |
|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | When `next_action` enters a BUILDING state, snapshot **only the tracked + clean** intersection: `git ls-files --modified --others --exclude-standard` minus current dirty set. Persist this as `STATE.json["build_baseline"] = { "started_at": <iso>, "preexisting_dirty": [<paths>] }`. The set of files that were dirty *before* the build conversation is the gate's exclusion list. |
| `src/pathly_orchestrator/fsm.py` | `_scope_clean` rewrites: read `STATE.json["build_baseline"]["preexisting_dirty"]` and subtract it from the `git diff --name-only HEAD` output. The result is "files the builder added or touched during this conversation." Compare *that* set against `declared`. Drop the `_is_exempt` hack for `src/pathly_orchestrator/` (that exemption was masking exactly this bug). Keep `pathly/plans/` and `*.tsbuildinfo` exemptions — they are genuine non-user artifacts. |
| `src/pathly_orchestrator/fsm_ops.py` | At `complete_stage` end (line 539), clear `build_baseline` along with `conv_start_sha` so the next conversation re-baselines fresh. |

Signature: `_scope_clean(storage_path, scope_file, preexisting_dirty: set[str] | None) -> bool`
— same return semantics, swap the third arg from `baseline_sha: str` to a path
set. `run_gates` (`fsm.py:453-460`) changes its STATE.json read from
`conv_start_sha` to `build_baseline.preexisting_dirty`.

```
Before:                              After:
─────────────────────                ──────────────────────────────
HEAD@conv_start ──► diff(working)    ls-files dirty @ conv_start
   ▲                                    ▲ persisted as exclusion set
   already lies about working dir       ▲
                                        diff(HEAD) - preexisting = touched
                                            ▲
                                            true set of conv work
```

### Tradeoffs

- **Snapshot races.** If the user edits a file between `next_action`'s baseline
  snapshot and the builder's first edit, that file gets exempted as "preexisting
  dirty" and any builder change to it won't be flagged. Acceptable — the gate
  is about preventing builder *runaway*, not catching every concurrent human
  edit. The plan already enumerates files the builder is allowed to touch in
  `CONVERSATION_PROMPTS.md`; this is belt-and-braces.
- **`build_baseline.preexisting_dirty` can be large.** A messy working tree
  could push STATE.json into the multi-KB range. Bound it: store a sorted set
  with no duplicates; truncate at 500 entries and log a `GATE_DEGRADED` event
  beyond that (gate falls back to permissive).
- **Untracked-file handling is delicate.** `git diff --name-only HEAD` does NOT
  show untracked files. We need `git status --porcelain=v1 -z` (which does) to
  catch builders who silently create new untracked files outside scope. That
  is a separate diff path from current code, so it adds complexity.

### Alternative considered

**Have the builder write a `BUILDER_TOUCHED.md` manifest at end of run** — list
every file the builder edited, gate compares that list to scope. Rejected:
relies on the builder being honest. The whole point of an enforcement gate is
to verify, not trust. Filesystem state at gate-eval time is the only reliable
signal.

---

## Problem 3 — MORE_CONVS_NEEDED.md is too implicit

### Root cause

`src/pathly_data/core/flows/team.flow.yaml:69-73`:

```yaml
REVIEWING:
  on_artifact:
    REVIEW_FAILURES.md: BUILDING
    MORE_CONVS_NEEDED.md: BUILDING
  default: TESTING
```

The reviewer must remember to write `MORE_CONVS_NEEDED.md` to route back to
BUILDING (per `src/pathly_data/core/skills/team/review.md:177`). If the reviewer
forgets, `on_artifact` finds nothing, `default: TESTING` fires, and the FSM
advances past the remaining conversations. The FSM has no idea that the plan
declared N conversations — that data lives only in `PROGRESS.md` rows, which
the FSM doesn't read.

### Proposed solution

Make conversation count a first-class FSM concept: read it from the plan once,
persist to STATE.json, and route on it explicitly. Keep `MORE_CONVS_NEEDED.md`
as a backwards-compat fallback for one release cycle.

| File | Change |
|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | New helper `_count_planned_convs(storage_path: Path) -> int`: count `\| [0-9]+ \|` rows in `PROGRESS.md`; return 0 if absent (legacy single-conv flow). Called once on first `next_action` for the feature; persisted to `STATE.json["convs_total"]` and `STATE.json["convs_done"] = 0`. |
| `src/pathly_orchestrator/fsm.py` | In `evaluate_transition_rules`, after the existing `on_artifact` check, add a fourth level **`on_state_counter`**: rule like `{"field": "convs_done", "lt": "convs_total", "next": "BUILDING"}`. Strictly compares two STATE.json fields. Returns next-state string if condition matches, else falls through to next rule level. |
| `src/pathly_data/core/flows/team.flow.yaml` | Rewrite REVIEWING rule: `on_state_counter` checks `convs_done < convs_total → BUILDING`; existing `on_artifact: MORE_CONVS_NEEDED.md: BUILDING` stays as fallback for one release; `default: TESTING`. |
| `src/pathly_orchestrator/fsm.py` | `run_transition_actions`: extend `update_progress` action — when `mark: conv_done`, increment `STATE.json["convs_done"]` (atomic read-modify-write inside the existing action). |
| `src/pathly_data/core/skills/team/review.md` | Remove the "write MORE_CONVS_NEEDED.md" instruction from line 177. The reviewer no longer needs to think about routing — it's driven by the counter. Note this as a backwards-incompatible skill change. |

```
Old routing (implicit, marker-driven):
  reviewer ──writes──► MORE_CONVS_NEEDED.md ──► FSM checks file ──► BUILDING
                       (easy to forget)

New routing (explicit, counter-driven):
  PROGRESS.md ──counted at next_action──► STATE.json.convs_total
  transition_action ──increments──► STATE.json.convs_done
  evaluate_transition_rules ──reads counter──► BUILDING or TESTING
```

### Tradeoffs

- **Two sources of truth: PROGRESS.md rows vs STATE.json.convs_total.** If a
  user manually edits PROGRESS.md mid-feature to add a conversation, FSM won't
  notice (snapshot is frozen at first `next_action`). Mitigate: re-read on
  every `next_action` and warn if `len(rows) != convs_total`. Don't auto-fix —
  let the user explicitly reset via a CLI flag if they meant it.
- **New transition rule level (`on_state_counter`) means new evaluator code
  and new tests.** Higher blast radius than just adding a YAML key. But the
  current `on_artifact` mechanism cannot express "advance only if N conditions
  met" — we need a real comparator.
- **Backwards compat window for `MORE_CONVS_NEEDED.md`.** Reviewer skill change
  is technically breaking, but `on_artifact: MORE_CONVS_NEEDED.md: BUILDING`
  remains for one release so older reviewer outputs still route correctly.

### Alternative considered

**Reviewer becomes a `decide` block: ask the reviewer "more conversations
needed?" with options `{yes: BUILDING, no: TESTING}`.** Rejected: this is
already known information — the plan said how many conversations are needed
when it was written. Asking again is asking the reviewer to repeat what the
planner already declared, which is exactly the kind of implicit-context bug
we're trying to eliminate.

---

## Cross-cutting concerns

### Independence

```
Problem 1 ─── transport layer (skill markdown + fsm_http_client.py)
Problem 2 ─── gate logic (fsm.py + STATE.json schema)
Problem 3 ─── routing rules (fsm.py + fsm_ops.py + team.flow.yaml + STATE.json schema)
                                          ▲
                                          shared schema —
                                          but Problems 2 and 3
                                          add disjoint keys
                                          (preexisting_dirty vs convs_total)
```

Problems 1 and 2 are fully independent. Problems 2 and 3 both write to
STATE.json but to **disjoint keys**, so they don't merge-conflict. The only
ordering risk: both add new STATE.json keys that other code paths might enumerate.
Audit `pathly_orchestrator/eventlog.py:read_state` and the Studio renderer that
displays STATE.json to confirm tolerance for unknown keys (they should already
do `.get()` style access).

### Recommended conversation breakdown

Three conversations, one per problem. Order matters for one reason: Problem 1
makes iteration on Problems 2 and 3 less painful (no "FSM server unavailable"
mid-test). Recommendation:

| Conv | Problem | Scope | Risk |
|---|---|---|---|
| 1 | Auto-start | `fsm_http_client.py`, `fsm-call.md`, `http_server.py` (health route) | Low — internal to transport |
| 2 | Scope gate rewrite | `fsm.py` (`_scope_clean`, `run_gates`), `fsm_ops.py` (build_baseline persistence) | Medium — touches 15 gates tests |
| 3 | Multi-conv first-class | `fsm.py` (`evaluate_transition_rules`, `update_progress` action), `fsm_ops.py` (counter helper), `team.flow.yaml`, `review.md` | Medium-high — adds new rule level, modifies core flow |

### Prerequisite reading for builders

- All three convs: `src/pathly_orchestrator/CLAUDE.md` (HTTP contract, decision field semantics).
- Conv 2 & 3: `tests/test_gates.py` and `tests/test_fsm_ops.py` end-to-end —
  understand the existing test contract before changing the implementation.
- Conv 3: `src/pathly_data/CLAUDE.md` adapter sync rule — any change to
  `core/skills/team/review.md` requires running `pathly-setup claude --apply`
  and `python -m build` to propagate to the codex and copilot adapters.

---

## Red flags to watch for

### Tests that will break or need extension

| Test | Why it might break | Likely action |
|---|---|---|
| `tests/test_gates.py::test_scope_gate_pass` (line 229) | Uses `conv_start_sha` directly; mocks `git diff` | **Will break.** Rewrite to seed `build_baseline.preexisting_dirty` and mock `git diff HEAD`. |
| `tests/test_gates.py::test_scope_gate_fail_undeclared_path` (line 256) | Same as above | **Will break.** Same rewrite. |
| `tests/test_gates.py::test_scope_gate_no_baseline_sha` (line 313) | Asserts a `no_baseline_sha` GATE_SKIPPED event | **Will break by definition.** Replace with `no_build_baseline` — emit `GATE_SKIPPED` reason when `build_baseline` is absent (legacy STATE.json). |
| `tests/test_gates.py::test_scope_gate_no_declared_scope` (line 292) | Untouched by changes | Should pass. Verify. |
| `tests/test_fsm_ops.py` (20 tests) | None directly reference `conv_start_sha`; only `complete_stage`/`next_action` envelope | Should pass. STATE.json key additions don't break existing assertions because tests use `.get()` or specific-key checks. **Verify** `test_next_action_initial_state` still passes after `build_baseline` is added to STATE.json. |
| New tests required for Conv 3 | `on_state_counter` evaluator level | Add at minimum: counter-met routes to next, counter-unmet stays, missing counter falls through to next rule level. |

### Adapter cross-impact (codex, copilot)

- Conv 1's `fsm-call.md` change: skill content is in `core/`, so codex and
  copilot adapters auto-rebuild via `python -m build`. **No manual `_meta/`
  edits required.** Verify by running `pathly-setup claude --apply` and
  diffing `adapters/codex/_meta/` and `adapters/copilot/_meta/`.
- Conv 3's `review.md` change: same — core file, both adapters rebuild from it.
- **scope_gate behavior is shared across adapters.** No adapter overrides the
  gate. The `_is_exempt` list at `fsm.py:424-429` mentions
  `src/pathly_orchestrator/` — that was added because the FSM was self-modifying
  during the enforcement-gates feature. Conv 2's rewrite removes that
  exemption; double-check no adapter feature still relies on it.

### Schema migration concerns

Old STATE.json files in `pathly/plans/*/` lack `build_baseline` and
`convs_total`. Both gates must treat missing keys as "skip with logged event"
(matches existing `no_baseline_sha` behavior). Do **not** auto-write new keys
into old STATE.json files — let them re-baseline on next `next_action`.

### Observable failure mode if Conv 3 ships before Conv 2

Counter-driven REVIEWING→BUILDING loop. The reviewer routes back to BUILDING.
The builder runs in a working tree that has the *previous* conversation's
edits as "preexisting dirty" — and the current scope_gate (still SHA-based)
treats those as in-scope falsely. The fix shipped in Conv 2 supersedes this,
but for the interim, the gate is no more wrong than today. Acceptable.

### Observable failure mode if Conv 2 ships before Conv 3

None. Conv 2 is self-contained.

### Final caution

The `_is_exempt` block at `fsm.py:424-429` currently exempts
`src/pathly_orchestrator/` from the scope gate. Removing that exemption in
Conv 2 means **the FSM cannot modify itself without declaring those paths in
`CONVERSATION_PROMPTS.md`.** That's the desired behavior, but it means Conv 2
and Conv 3's own `CONVERSATION_PROMPTS.md` files must list `src/pathly_orchestrator/fsm.py`
and `src/pathly_orchestrator/fsm_ops.py` explicitly. If they don't, the gate
will fail the build of these very fixes.
