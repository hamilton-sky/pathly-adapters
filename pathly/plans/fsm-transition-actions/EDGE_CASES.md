# EDGE_CASES.md — fsm-transition-actions

_Failure modes and edge cases. Each item names the story it applies to and the
expected behavior. Items marked [GUARD] have an existing guard in orchestrator.md that
must be preserved through the refactor._

---

## 1. Schema validation — malformed transition_actions

**Applies to:** S1.1, S3.1

### 1a. Key present but value is wrong type

```yaml
transition_actions: "BUILDING->REVIEWING"  # string, not map
```

- Conv 1-2 (YAML-only): orchestrator reads the key as a scalar, list lookup fails, executor
  falls through as no-op. No crash — but behavior is silently wrong.
- Conv 3 (validator): `validate_flow` must type-check the value and error: "transition_actions
  must be a mapping, got string."

### 1b. Unknown action type

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: run_shell_command   # not in vocabulary
      cmd: "echo hello"
```

- Conv 2 (executor): orchestrator encounters an unknown `type` value. Behavior: halt and
  report "unknown transition action type: run_shell_command". Do not silently skip.
- Conv 3 (validator): `validate_flow` errors at load time: "unknown action type
  'run_shell_command'; allowed: git_commit, update_progress, archive_artifacts."

### 1c. git_commit action missing required `message` field

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: git_commit
      # message omitted
```

- Conv 2 (executor): orchestrator attempts `git commit -m ""` or equivalent — git will
  likely reject an empty message. Orchestrator must treat this as an action failure: halt
  and report "git_commit action requires a non-empty message field."
- Conv 3 (validator): `validate_flow` errors: "git_commit action is missing required field
  'message'."

### 1d. update_progress missing required `mark` field

```yaml
- type: update_progress
  # mark omitted
```

- Same pattern: executor halts and reports; validator errors at load time.

### 1e. Transition key format is invalid

```yaml
transition_actions:
  "BUILDING REVIEWING":   # missing ->
    - type: git_commit
      message: "..."
```

- Conv 3 (validator): `validate_flow` errors: "transition_actions key 'BUILDING REVIEWING'
  is not a valid FROM->TO or ->TO format."
- Conv 2 (executor): the malformed key will simply never match any lookup — treated as
  dead YAML that never fires. Silently wrong without validator; this is acceptable before
  Conv 3 lands.

---

## 2. Execution ordering — mid-sequence failure

**Applies to:** S2.1

### 2a. git commit fails (e.g. nothing to commit, merge conflict, hook rejection)

A transition fires and its action list is:

```yaml
- type: update_progress
  mark: conv_done
- type: git_commit
  message: "feat: complete building stage"
- type: archive_artifacts
```

If `git_commit` fails:
- `update_progress` has already run — PROGRESS.md is already updated.
- `archive_artifacts` has NOT yet run.
- **Expected behavior:** orchestrator halts and reports the git failure. It does NOT
  roll back the `update_progress` write. It does NOT skip ahead to `archive_artifacts`.
- The operator must fix the git issue and resume. STATE.json was written before the action
  sequence began, so the FSM state is consistent; only the side effects are partial.
- This matches the existing "halt-and-report" behavior for unexpected errors (orchestrator
  already does this for sub-agent failures).

### 2b. archive_artifacts fails (target directory missing, permission error)

- Same halt-and-report applies.
- Actions before the failure are not rolled back.
- The run is in a deterministic partial state: the operator can manually create the
  directory and re-run the archiving, then resume.

### 2c. Idempotency concern on resume

If the operator resumes after a mid-sequence failure, the executor re-runs the full action
list for that transition (because STATE.json records the new state, not the action
progress). This means:
- `update_progress` may be called twice — implementation must be idempotent (writing DONE
  to an already-DONE row is harmless).
- `git_commit` will fail again if there is nothing new to commit — implementation should
  treat "nothing to commit" as a non-fatal no-op, not a halt.
- `archive_artifacts` may write duplicate files — naming convention
  (`FILENAME_conv<N>_attempt<M>`) already handles this if attempt number is incremented.

---

## 3. Wildcard vs exact match — resolution order

**Applies to:** S2.1, S3.1

### 3a. Both exact and wildcard key are present

```yaml
transition_actions:
  "BUILDING->REVIEWING": [...]   # exact
  "->REVIEWING": [...]           # wildcard
```

When the transition `BUILDING->REVIEWING` fires:
- **Expected behavior:** exact key wins; wildcard key is NOT also executed.
- Rationale: wildcard means "any transition entering REVIEWING that has no explicit
  rule." Running both would cause double-execution and unexpected ordering.
- Executor lookup order: check exact key first; if found, execute it and stop. Check
  wildcard only if no exact key matched.

### 3b. Only wildcard present

```yaml
transition_actions:
  "->DONE": [...]
```

Any transition entering DONE fires this list regardless of origin state. This is the
intended archive_artifacts pattern.

### 3c. Multiple wildcards for the same destination

```yaml
transition_actions:
  "->DONE": [...]
  "->REVIEWING": [...]
```

Each wildcard is independent. They only fire when the destination matches. No conflict.

### 3d. Wildcard source (unsupported)

`"BUILDING->"` (wildcard destination) is not in the spec and must not be added. The
validator should error if such a key appears; the executor should treat it as dead YAML.

---

## 4. Empty or absent transition_actions

**Applies to:** S1.1, S2.1

### 4a. Key absent from flow YAML

```yaml
# no transition_actions key at all
```

- Conv 2 (executor): reads `transition_actions` from flow YAML → key not present → treat
  as empty map `{}` → all transitions are no-op. Must not raise a KeyError or crash.
- Conv 3 (validator): warns "transition_actions not found in flow YAML" but does not error.
  This allows future read-only or audit flows that have no side effects.

### 4b. Key present but empty map

```yaml
transition_actions: {}
```

- Executor: same as absent — all transitions no-op. No error.
- Validator: no warning (the author explicitly declared an empty map; that is intentional).

### 4c. Key present with some entries, others absent

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: git_commit
      message: "feat: complete building stage"
  # RETRO->DONE has no entry
```

- Executor: `RETRO->DONE` fires with no matching actions — no-op for that transition.
  Only `BUILDING->REVIEWING` fires its declared git_commit. Expected behavior: no error,
  no warning at runtime.

---

## 5. Conv 3 blocker — validate_flow_cli does not yet exist

**Applies to:** S3.1

Conversation 3 depends on `fsm-configurable` Phase 5c delivering `validate_flow_cli` and
`_REQUIRED_FLOW_KEYS` in `src/pathly_orchestrator/state.py`.

**If someone attempts Conversation 3 before Phase 5c is DONE:**

- `state.py` does not contain `validate_flow_cli` or `_REQUIRED_FLOW_KEYS`.
- Any edit to `state.py` for `transition_actions` validation will have no valid insertion
  point — the diff will be structurally wrong.
- `pathly-validate-flow` CLI entrypoint does not exist — verify commands will fail with
  "command not found."

**Guard:** Do not begin Conversation 3. The IMPLEMENTATION_PLAN.md BLOCKED notice is the
gate. The operator must confirm `fsm-configurable` is fully DONE before issuing the Conv 3
prompt.

**Detection:** Run `grep "_REQUIRED_FLOW_KEYS" src/pathly_orchestrator/state.py` before
starting Conv 3. If it returns no output, Phase 5c has not landed — halt.

---

## 6. autoFlow + feedback file guard — git_commit must not fire when feedback is present

**Applies to:** S2.1

**[GUARD — orchestrator.md line 139]**

The existing orchestrator rule states: when a feedback file triggers re-routing to a
fixing agent, no commit and no PROGRESS.md update until the feedback is resolved and the
state advances cleanly.

This guard must survive the Conv 2 refactor. Specifically:

- If `REVIEW_FAILURES.md` or `ARCH_FEEDBACK.md` is present in the feedback directory when
  a `git_commit` transition action would otherwise fire, the executor must skip the
  git_commit action (and log that it was suppressed due to an active feedback file).
- The same skip applies to `update_progress` — PROGRESS.md must not be marked DONE while
  a feedback file is unresolved.
- `archive_artifacts` is unaffected by this guard — archiving feedback files is exactly
  what the dual-write rule requires during a feedback cycle.

**Implementation note for Conv 2:** the executor block inserted into orchestrator.md must
include a check: "if any feedback file exists in `<storage_path>/feedback/`, skip
git_commit and update_progress actions for this transition; proceed with archive_artifacts
only." This check is applied per-action, not per-transition.

**Feedback files that trigger this guard:**
- `REVIEW_FAILURES.md`
- `ARCH_FEEDBACK.md`
- `TEST_FAILURES.md`
- `IMPL_QUESTIONS.md`
- `DESIGN_QUESTIONS.md`
- `HUMAN_QUESTIONS.md`
