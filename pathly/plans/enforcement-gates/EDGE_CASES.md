# Enforcement Gates — Edge Cases

## Category 1: verify_gate sentinel robustness

### EC-1.1: `RESULT: PASS` appears only in the body, not on line 1

- **Trigger**: Builder writes a VERIFY.md that includes `RESULT: PASS` inside a failure explanation block.
- **Current behavior (without fix)**: Substring match would pass the gate incorrectly.
- **Expected behavior**: Gate fails — sentinel must be the exact content of the first non-blank line.
- **Handled in**: Phase 1 — `_verify_passed` uses first-non-blank-line exact match, not substring.

### EC-1.2: `VERIFY.md` is empty

- **Trigger**: Builder creates `VERIFY.md` as a placeholder but writes nothing.
- **Expected behavior**: Gate fails (no first non-blank line to match).
- **Handled in**: Phase 1 — `_verify_passed` returns `False` if file is empty.

### EC-1.3: `VERIFY.md` is absent entirely

- **Trigger**: Builder skips the verify step.
- **Expected behavior**: Gate fails immediately — file existence check precedes content check.
- **Handled in**: Phase 1 — `_verify_passed` returns `False` if path does not exist.

---

## Category 2: scope_gate diff baseline

### EC-2.1: Baseline SHA is missing from STATE.json

- **Trigger**: Older pipeline run where `conv_start_sha` was not written, or first conversation.
- **Expected behavior**: `GATE_SKIPPED` event emitted with `reason: "no_baseline_sha"`, gate passes (does not block).
- **Handled in**: Phase 4 — SHA read with a `None` default; `_scope_clean` emits GATE_SKIPPED and returns True.

### EC-2.2: `git diff` fails (not a git repo, detached HEAD, etc.)

- **Trigger**: Running in a non-git environment or corrupted repo state.
- **Expected behavior**: `GATE_SKIPPED` with `reason: "git_diff_failed"`, gate passes.
- **Handled in**: Phase 4 — subprocess returncode check; on failure emit GATE_SKIPPED.

### EC-2.3: Baseline SHA points to a commit that includes prior-conversation files

- **Trigger**: SHA was set at the wrong point (not pinned to conversation start).
- **Expected behavior**: Gate may report false positives (sees conv-1 files in a conv-2 diff).
- **Status**: Mitigation is correct SHA pinning by the orchestrator at conversation start. If `conv_start_sha` is absent, scope_gate skips rather than producing a false result.

---

## Category 3: scope_gate — no declared scope

### EC-3.1: `CONVERSATION_PROMPTS.md` has no parseable file list

- **Trigger**: Plan was written without explicit file declarations.
- **Expected behavior**: `GATE_SKIPPED` with `reason: "no_declared_scope"`. Operator sees the skip in EVENTS.jsonl — enforcement is absent but not silent.
- **Handled in**: Phase 4 — parser finds no matching lines → GATE_SKIPPED emitted.

### EC-3.2: `CONVERSATION_PROMPTS.md` does not exist at all

- **Trigger**: Gate configured but scope file missing.
- **Expected behavior**: Treated as no declared scope → `GATE_SKIPPED`.
- **Handled in**: Phase 4 — read failure falls through to the "no declared paths" branch.

### EC-3.3: `CONVERSATION_PROMPTS.md` is restructured or pruned mid-feature

- **Trigger**: A planner or user edits `CONVERSATION_PROMPTS.md` (e.g. reformats file lists, removes backtick/dash prefixes) after the YAML gate is already configured.
- **Expected behavior**: Parser finds no matching lines → `GATE_SKIPPED`. The gate silently stops enforcing scope without any code change.
- **Risk**: This is a plan-file-as-enforcement-input fragility. A doc edit can disable the gate.
- **Mitigation**: If scope enforcement is critical, prefer a dedicated `SCOPE.md` file (one path per line, no Markdown decoration) as the `scope_file` target — it is less likely to be reformatted and easier to parse reliably. The YAML `scope_file` field is configurable; swap the value without touching gate logic.
- **Status**: Not handled automatically — operator awareness required. Logged here so the decision is visible.

---

## Category 4: Gate ordering and commit timing

### EC-4.1: Gate fails after the commit action has already run

- **Trigger**: Gates placed after `run_transition_actions` instead of before.
- **Expected behavior**: Should never happen — gates run before `run_transition_actions`, so a failing build is never committed.
- **Handled in**: Phase 2 — insertion point in `complete_stage` is explicitly before `run_transition_actions(...)`.

### EC-4.2: Multiple gates fail in the same transition

- **Trigger**: Both `verify_gate` and `scope_gate` fail on `BUILDING->REVIEWING`.
- **Expected behavior**: First failure stops evaluation (fail-fast). Only one feedback file is written per `complete_stage` call. The second failure is caught on the next call after the first is resolved.
- **Status**: Intentional design. Documented in comment near `run_gates()`. Collecting all failures would require a new multi-failure feedback format.

---

## Known Limitations

- `scope_gate` does not validate staged-but-not-committed changes — only committed diff from baseline SHA.
- Gate ordering within a transition is YAML insertion order; there is no explicit priority field.
- `verify_gate pass_marker` is configurable in YAML but the FSM has no awareness of what a "valid" marker looks like — misconfiguring the marker string bypasses the gate silently.
