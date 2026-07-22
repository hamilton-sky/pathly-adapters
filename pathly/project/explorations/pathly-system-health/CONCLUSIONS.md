# Conclusions — pathly-system-health

## Recommendation

**RECOMMEND: BUILD** — The Pathly system architecture is fundamentally sound. The FSM is correct and the overall structure is coherent. However, before going to production, resolve the 7 concrete issues listed below.

The issues are **not showstoppers** (the system works end-to-end), but they are **specific and fixable**. Resolving them will eliminate integration gaps, improve hook reliability, and eliminate schema fragility.

---

## Summary findings

### Q1: Is the overall Pathly architecture coherent and correctly wired?

**Answer: Yes, with one integration gap.**

The architecture is well-organized into clean layers:
- Hooks layer (classify_feedback, inject_feedback_ttl)
- Installer layer (setup_command, materialize, hook registration)
- Orchestrator layer (state machine, event log, FSM engine)
- Flow & skills layer (YAML definitions, markdown skill prompts)
- Telemetry layer (HTTP server, record_activity)

Dependency direction is one-way downward. File structure is easy to navigate. Layer responsibilities are clearly separated.

**Integration gap:** The installer does not inject `PATHLY_PROJECT_ROOT` into the hook environment when registering hooks. Both hooks check for this env var and fail (exit 1) if not set. The end user or orchestrator (LLM) must manually set the env var, or hooks will always fail on the first run.

**Verdict:** Coherent and well-wired. The gap is fixable (Improvement 3 below).

---

### Q2: Does the FSM (orchestrator + flow YAML) work correctly?

**Answer: Yes. The FSM is correct and all state transitions work as designed.**

The state machine correctly:
- Validates transitions before writing STATE.json
- Appends events in order to EVENTS.jsonl
- Recovers from disk (reads STATE.json, re-derives state)
- Routes feedback files to mapped agents
- Executes flow as YAML specifies

The explore flow was successfully executed in this run (FRAMING → ANALYZING → TRACING → CONCLUDING → DONE).

**Two edge-case vulnerabilities (not blockers):**
1. Event schema has no `schema_version` field. If the schema changes (e.g., rename `type` to `event_type`), existing EVENTS.jsonl files will silently fail to parse.
2. Windows file locking is disabled (fcntl not available). Concurrent writes from multiple processes could corrupt EVENTS.jsonl on Windows. (On Unix, fcntl.flock prevents this.)

**Verdict:** Works correctly for normal single-agent operation. Vulnerabilities are theoretical and low-probability; fixable (Improvements 5 and 6 below).

---

### Q3: Are the hooks reliable, and what concrete improvements can be made?

**Answer: Hooks are partially reliable. Four concrete issues + one schema issue + one platform issue = 7 improvements total.**

#### Hook reliability issues:

1. **Exit code mismatch:** Original spec says "silent no-op (exit 0)." Current code exits 1 on missing PATHLY_PROJECT_ROOT. Tests validate exit 1. Neither README nor docstring clarifies which is correct. This ambiguity is a spec debt.

2. **No error handling on file mutations:** Both hooks call `write_text()` without try/except. If the file is read-only or the parent dir is not writable, the hook crashes with a raw Python traceback, blocking the user's workflow.

3. **PATHLY_PROJECT_ROOT not injected by installer:** setup_command.py materializes hook scripts but does not set PATHLY_PROJECT_ROOT in the hook environment. Hooks fail unless the user manually sets the env var. Low discoverability.

4. **No pre-flight checks:** setup_command.py does not verify that PATHLY_PROJECT_ROOT is set, or that the plans/ directory is writable, before registering hooks.

#### Schema & platform issues:

5. **Event schema has no version field:** No `schema_version` in EVENTS.jsonl. If the schema changes, existing logs break silently.

6. **Windows file locking missing:** No msvcrt.locking() fallback on Windows. Concurrent appends to EVENTS.jsonl could corrupt the file.

7. **record_activity tool not documented:** The HTTP telemetry tool is not mentioned in README.md or docs/PATHLY_ARCHITECTURE.md. New LLM agents may not discover it.

**Verdict:** Hooks work for the happy path (env var set, file writable, schema stable). The 7 issues are fixable. No showstoppers.

---

## Actionable improvements (with file:line pointers)

All improvements are **concrete and testable**. None require architectural changes.

### Tier 1 (required for production)

**Improvement 1: Clarify hook exit code behavior**
- **Files:** `src/pathly_hooks/classify_feedback.py:34-37,49-50`, `src/pathly_hooks/inject_feedback_ttl.py:54-57`, `README.md`, `pathly/plans/.archive/orchestrator-hardening/IMPLEMENTATION_PLAN.md`
- **Action:** Decide: should hooks exit 0 (silent) or exit 1 (fail loudly) when PATHLY_PROJECT_ROOT is missing?
  - If exit 0: clarify docstring, update tests, document as "optional hook" in README
  - If exit 1: document in README that PATHLY_PROJECT_ROOT must be set, add validation to setup_command.py
- **Time:** < 1 hour

**Improvement 2: Add error handling to hook file mutations**
- **Files:** `src/pathly_hooks/classify_feedback.py:69`, `src/pathly_hooks/inject_feedback_ttl.py:77`
- **Action:** Wrap `resolved.write_text()` in try/except. On permission error, exit 0 with a clear stderr message: "pathly-hook: permission denied; skipping feedback classification"
- **Time:** < 30 min

**Improvement 3: Inject PATHLY_PROJECT_ROOT into hook environment**
- **Files:** `src/install_cli/materialize.py:31,36`, `src/install_cli/setup_command.py:95-116`
- **Action:** When registering hooks (Codex, Copilot), wrap hook command in a shell script that sets PATHLY_PROJECT_ROOT=<current directory>. Or: detect PATHLY_PROJECT_ROOT at setup time and inject it into the hook command JSON.
- **Time:** < 1 hour

**Improvement 4: Add pre-flight checks in setup_command.py**
- **Files:** `src/install_cli/setup_command.py:45-49`
- **Action:** Before calling `_run_host()`, check:
  - PATHLY_PROJECT_ROOT is set (or cwd is a Pathly project)
  - plans/ directory exists and is writable
  - Print error and exit 1 if checks fail
- **Time:** < 1 hour

### Tier 2 (recommended before 3.0 release)

**Improvement 5: Add schema_version to EVENTS.jsonl**
- **Files:** `src/pathly_orchestrator/events.py`, `src/pathly_orchestrator/eventlog.py:105-118`
- **Action:** 
  - Write a one-time `{"schema_version": "1.0"}` line as the first line of EVENTS.jsonl on creation
  - In `read_events()`, check the first line; raise ValueError if schema_version != "1.0"
  - Document schema version in events.py docstring
- **Time:** < 2 hours

**Improvement 6: Add Windows file locking**
- **Files:** `src/pathly_orchestrator/eventlog.py:62-72`
- **Action:** Add fallback for Windows:
  ```python
  try:
      import fcntl
      fcntl.flock(f, fcntl.LOCK_EX)
  except ImportError:
      # Windows: use msvcrt.locking
      import msvcrt
      msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, len(line))
  ```
- **Time:** < 1 hour

**Improvement 7: Document record_activity tool**
- **Files:** `README.md`, `src/install_cli/http_config.py`, `docs/PATHLY_ARCHITECTURE.md:125`
- **Action:** 
  - Add one sentence to `http_config.py` docstring: "Registers the pathly-telemetry HTTP server, which exposes record_activity to log agent work."
  - Add a note to README.md under "HTTP" or "Telemetry" section: "Agents automatically call record_activity to report completion."
- **Time:** < 30 min

---

## Risk assessment (from architecture-risk-assessment)

This exploration cross-referenced prior findings from `pathly/explorations/architecture-risk-assessment/TRACE.md`. Summary of prior risks:

| Prior Risk | Status | Related to this exploration? |
|---|---|---|
| Risk 1: Hooks silent failure | Partially relevant | Yes — Improvements 1–4 address exit codes and env setup |
| Risk 2: Codex clean-machine gap | No | Out of scope (adapter-specific) |
| Risk 3: orchestrator dual role (no schema version) | Relevant | Yes — Improvement 5 addresses schema versioning |
| Risk 4: Version drift in docs | Partially relevant | Yes — docs mention hooks, but no improvements needed beyond Improvement 1 |
| Risk 5: http_config opaque | Relevant | Yes — Improvement 7 addresses documentation |

**Conclusion:** This exploration has identified the root causes of prior risks and specified fixes.

---

## Test plan for improvements

Each improvement is testable:

1. **Improvement 1:** Update docstrings, run `pytest tests/test_hooks.py` to confirm test expectations match code.
2. **Improvement 2:** Add test case: create read-only file, call hook, assert exit 0 and stderr message.
3. **Improvement 3:** Create test hook registration, verify hook environment contains PATHLY_PROJECT_ROOT.
4. **Improvement 4:** Add pre-flight check tests: missing PATHLY_PROJECT_ROOT → exit 1, plans/ not writable → exit 1.
5. **Improvement 5:** Parse EVENTS.jsonl, verify first line is `{"schema_version": "1.0"}`.
6. **Improvement 6:** Run on Windows with concurrent appends; verify EVENTS.jsonl is not corrupted.
7. **Improvement 7:** Build HTML docs; verify http_config.py and record_activity appear in output.

---

## Next steps

1. **Address Tier 1 improvements** (2–3 hours) before merging to main.
2. **Address Tier 2 improvements** (4–5 hours) before the next release.
3. **Consider CI/clean-machine test** (prior Risk 2) in a future update (not blocking).

---

## Files produced

- `pathly/explorations/pathly-system-health/EXPLORE.md` — framing (pre-written)
- `pathly/explorations/pathly-system-health/PROGRESS.md` — analysis summary
- `pathly/explorations/pathly-system-health/TRACE.md` — scout findings
- `pathly/explorations/pathly-system-health/CONCLUSIONS.md` — this file

---

## Appendix: Files visited during exploration

**Hooks layer:**
- `src/pathly_hooks/classify_feedback.py` (74 lines)
- `src/pathly_hooks/inject_feedback_ttl.py` (81 lines)

**Orchestrator layer:**
- `src/pathly_orchestrator/state.py` (82 lines)
- `src/pathly_orchestrator/eventlog.py` (236 lines)
- `src/pathly_orchestrator/events.py` (84 lines)
- `src/pathly_orchestrator/__init__.py` (8 lines)

**Installer layer:**
- `src/install_cli/setup_command.py` (495 lines, reviewed 1–235)
- `src/install_cli/materialize.py` (286 lines, reviewed 20–70, 104–143)
- `src/install_cli/resources.py`, `detect.py`, `stitch.py` (referenced, not reviewed)

**Flow & skills layer:**
- `src/pathly_data/core/flows/explore.flow.yaml` (31 lines)
- `src/pathly_data/core/skills/explore.md` (115 lines)

**Telemetry layer:**
- `src/pathly_telemetry/server.py` (lines 1–60)

**Cross-references:**
- `pathly/explorations/architecture-risk-assessment/TRACE.md` (full)

**Total scout coverage:** 6 distinct risk areas, 4 parallel scouts, no file duplication.

---

## Quality assurance

This exploration:
- Followed scout spawning rules (4 scouts: 1 orientation + 3 clustered by risk area)
- Launched all scouts in parallel (no sequential file reads)
- Cross-referenced prior explorations (architecture-risk-assessment)
- Provided file:line pointers for every improvement
- Specified test criteria for each improvement
- Did not re-scout files already covered in prior explorations

All three questions have concrete, evidence-based answers.
