# Pathly System Improvement Recommendations

_Written 2026-05-28. Covers agents, skills, flow YAML design, and the Python FSM engine._

---

## Summary

The recommendations below are grouped by area. Each entry has an impact/effort
rating and — for Python fixes — shows the exact code change.

---

## 1. Agents & Skills

### 1.1 Agent Context Bridging — HIGH impact / MEDIUM effort

**Problem:** Each agent conversation starts cold. The FSM knows the current state,
retry count, open feedback files, last events, and plan paths — but none of this is
injected into the agent's context at conversation start. Agents re-ask questions
already answered in previous stage feedback.

**Recommendation:** Extend the `next_action` response to include a structured
`stage_brief` block: current state, retry count, open feedback file names, the last
3 EVENTS.jsonl entries, and the relative path to the plan directory. Each agent
should be required to read this block before acting. The FSM already has all this
data — it just needs to format and include it in the instructions it returns.

---

### 1.2 Rigor Level Behavioral Specification — HIGH impact / LOW effort

**Problem:** `go.md` classifies intent and chooses nano/lite/standard/strict, but
the actual behavioral differences are not defined per agent. Does a `nano` builder
skip scouts? Does `lite` review skip the scope gate? This is left to each agent's
interpretation, producing inconsistent results.

**Recommendation:** Add a `rigor_contract` section to each agent file (or a shared
`rigor-levels.md` injected at install time) that defines what each level means for
that role:

| Role | nano | lite | standard | strict |
|---|---|---|---|---|
| builder | no scouts, ≤2 files | 1 scout allowed | up to 4 scouts | full scout + verify gate |
| reviewer | diff only | diff + arch rules | + scope gate | + security check |
| tester | smoke only | happy path | + edge cases | + regression suite |
| planner | skip storm | skip architect consult | full consult | + PO session |

---

### 1.3 `meet.md` Consultation Auto-Injection — MEDIUM impact / LOW effort

**Problem:** Consultations write to `pathly/plans/<feature>/consults/` as read-only
notes. Nothing surfaces them to the next builder. A user who consults the architect
gets advice the builder then ignores unless they manually read the folder.

**Recommendation:** The FSM's `next_action` response should include the contents
of the most recently written consult file (if any) in the `stage_brief`. The agent
instructions for `builder` and `planner` should explicitly state: "if `recent_consult`
is present in your stage brief, incorporate it before acting."

---

### 1.4 Feedback TTL and Stale-Feedback Warning — MEDIUM impact / LOW effort

**Problem:** `HUMAN_QUESTIONS.md` blocks the pipeline with no timeout or escalation.
`verify-state.md` checks for stale feedback, but it is entirely user-triggered. A
feedback file written hours ago and never addressed stalls the pipeline silently.

**Recommendation:** In `next_action`, when returning a blocked response, include a
`feedback_age_hours` field derived from the file's mtime. The skill layer should
surface a warning to the user if the age exceeds a threshold (e.g., 4 hours):
`"⚠ HUMAN_QUESTIONS.md has been open for 6h — review before continuing."` No auto-
resolution, just visibility.

---

### 1.5 Cross-Stage Lesson Injection — MEDIUM impact / LOW effort

**Problem:** `lessons.md` synthesizes patterns into `pathly/lessons/LESSONS.md`, but
this file is never automatically fed back into subsequent features. A planner starting
a new feature does not know what the last three features learned.

**Recommendation:** `plan.md` already reads `LESSONS.md` (the SKILLS_OVERVIEW shows
"Read LESSONS.md — silently apply injections"). Verify this is enforced in the actual
skill file and not just documented. If it is enforced, ensure `start.md` also surfaces
a one-line summary ("3 active lessons — planner will apply them") so users know the
system is learning. If it is not yet enforced, wire it in as a required pre-step in
`plan.md`.

---

### 1.6 Gate Expansion Beyond BUILDING→REVIEWING — MEDIUM impact / MEDIUM effort

**Problem:** `verify_gate` and `scope_gate` only fire on `BUILDING→REVIEWING`.
Other transitions rely on artifact presence alone. `PLANNING→DESIGNING` only checks
that `IMPLEMENTATION_PLAN.md` exists — not that it has any conversations defined.
Empty or placeholder artifacts gate through unnoticed.

**Recommendation:** Add lightweight content checks to key transitions in the flow YAMLs:

- `PLANNING→DESIGNING`: `on_content` check that `IMPLEMENTATION_PLAN.md` contains
  at least one `## Conversation` heading.
- `DESIGNING→BUILDING`: `on_content` check that `DESIGN.md` contains a `## Colors`
  or `## Layout` section.
- These are `on_content` rules — pure YAML, zero Python changes.

---

### 1.7 Director Correction Path — LOW impact / LOW effort

**Problem:** If `go.md`'s director routes to the wrong skill, the user must re-invoke
with a clearer prompt and gets no feedback on the routing decision.

**Recommendation:** Add a single routing-explanation line to the director's output
before it invokes the target skill:
`"Routing to build — classified as: resume-implementation. Wrong? Try /pathly plan <feature> instead."`
One sentence, states the classification, gives the correction path.

---

### 1.8 Debug Flow: Add REPRODUCING State — LOW-MEDIUM impact / LOW effort

**Problem:** `debug.flow.yaml` jumps from `PROBLEM → INVESTIGATING`. Reproducing the
bug is often the hardest step and is currently invisible — the scout goes straight
to root-cause analysis without confirming the bug is actually reproducible.

**Recommendation:** Add a `REPRODUCING` state between `PROBLEM` and `INVESTIGATING`:
- Agent: `tester` (read-only — confirm reproduction, write `REPRO.md`)
- On `[CONFIRMED]` → advance to `INVESTIGATING`
- On `[NOT REPRODUCED]` → write `HUMAN_QUESTIONS.md`, block pipeline
- On `[PARTIAL]` → advance with caveat note in `REPRO.md`

This makes debug sessions more rigorous and gives better artifacts for post-mortems.

---

### 1.9 Scout Protocol Simplification — LOW impact / LOW effort

**Problem:** The current scout rules impose complex cognitive load on the builder:
min 2 scouts when used, max 4, each covers 2-3 files, all launched in parallel in
a single message, no LLM reads while scouts are active. This is a lot to enforce
via natural-language instructions.

**Recommendation:** Replace the min-2 rule with a simpler "investigation budget":
the builder has a context budget of N file reads per conversation. Scouts are the
mechanism for spending it. Drop the minimum — if one scout covers everything needed,
that is valid. The maximum (4) and parallel-launch requirement stay, as they prevent
serial bottlenecks and token waste.

---

## 2. Python FSM Engine

Three concrete bugs were found in `fsm.py` and `fsm_ops.py`. The fixes are
already applied to the codebase (commit: see git log). This section documents
what they were and why they matter, plus additional hardening recommendations.

---

### 2.1 `_verify_passed` only checked the first non-empty line — FIXED

**File:** `src/pathly_orchestrator/fsm.py` — `_verify_passed()`

**Bug:** The function returned `True` or `False` on the first non-empty line of
`VERIFY.md`. If the agent wrote any content before the `RESULT: PASS` line (a
header, a summary, context notes), the gate would fail even though the result was
correct.

**Before:**
```python
for line in text.splitlines():
    if line.strip():
        return line.strip() == marker  # returns on FIRST non-empty line
return False
```

**After:**
```python
# Scan all non-empty lines — the marker may appear after front-matter or headers.
for line in text.splitlines():
    if line.strip() == marker:
        return True
return False
```

**Impact:** Builders whose `VERIFY.md` had any content above `RESULT: PASS` would
hit a spurious gate failure and be routed back to the building stage unnecessarily.

---

### 2.2 `assert` in production code path — FIXED

**File:** `src/pathly_orchestrator/fsm_ops.py` — `complete_stage()`

**Bug:** The transition resolution used a bare `assert` to validate the return type
of `evaluate_transition_rules`. Python `assert` statements are silently removed when
the interpreter runs with `-O` (optimize flag), meaning the check would disappear
in optimized production deployments, allowing a malformed return value to propagate
silently.

**Before:**
```python
assert isinstance(eval_result, str), f"Unexpected result type: {type(eval_result)}"
next_state = eval_result
```

**After:**
```python
if not isinstance(eval_result, str):
    raise RuntimeError(
        f"evaluate_transition_rules returned unexpected type {type(eval_result)!r}; "
        f"expected str or decide-dict"
    )
next_state = eval_result
```

---

### 2.3 `conv_start_sha` carried forward across state transitions — FIXED

**File:** `src/pathly_orchestrator/fsm_ops.py` — `complete_stage()`

**Bug:** `conv_start_sha` is written to `STATE.json` by `next_action` at the start
of each conversation, so the scope gate can baseline `git diff` against it. When
`complete_stage` transitions to the next state, it preserved `prior_state` — including
the old `conv_start_sha`. The next call to `next_action` checks
`if not prior_state.get("conv_start_sha")` and skips re-stamping because the field
is already present. This means conversations 2, 3, … all used the SHA from
conversation 1 as their baseline, causing the scope gate to diff against the wrong
commit.

**Before:**
```python
prior_state = state_before or {}
write_state(storage_path, next_state, prior_state)
```

**After:**
```python
prior_state = dict(state_before or {})
# Clear the per-conversation git baseline so the *next* conversation
# gets a fresh SHA stamp from next_action — not the previous conv's baseline.
prior_state.pop("conv_start_sha", None)
write_state(storage_path, next_state, prior_state)
```

**Impact:** Without this fix, the scope gate in conversation 3 would diff against the
SHA from conversation 1 and flag all files changed in conversations 1 and 2 as
out-of-scope violations, even if they were legitimately in scope for their respective
conversations.

---

### 2.4 Hardcoded scope gate exemptions — NOT YET FIXED

**File:** `src/pathly_orchestrator/fsm.py` — `_scope_clean()` — lines ~425-430

**Issue:** The `_is_exempt` function hardcodes two exemptions:
```python
def _is_exempt(p: str) -> bool:
    return (
        p.startswith("pathly/plans/")
        or p.startswith("src/pathly_orchestrator/")
        or p.endswith(".tsbuildinfo")
    )
```

`src/pathly_orchestrator/` is a Pathly-internal path that has no reason to be exempt
in user projects. This exemption exists because Pathly uses itself as its own test
bed. In a clean user project, this exemption is harmless but confusing.

**Recommendation:** Move exemptions to the flow YAML as a `scope_gate.exempt_prefixes`
list. Default to only `pathly/plans/` and `*.tsbuildinfo`. This makes the gate
behavior explicit and configurable without changing `fsm.py` for each project.

---

### 2.5 `route_feedback` silently ignores unrecognized feedback files — NOT YET FIXED

**File:** `src/pathly_orchestrator/fsm.py` — `route_feedback()`

**Issue:** If a feedback file exists whose name is not in `flow["feedback_routing"]`,
it is silently ignored and `route_feedback` returns `None`. The pipeline proceeds
as if no feedback exists, potentially advancing past unresolved issues.

**Recommendation:** After checking all known routing keys, if unmatched `.md` files
remain in `feedback/`, return a fallback blocked response routing to `human`:
```python
# Fallback: unrecognized feedback file — surface to human rather than ignoring
unmatched = md_files - set(
    (stem if stem.endswith(".md") else f"{stem}.md")
    for stem in feedback_routing
)
if unmatched:
    filename = sorted(unmatched)[0]
    return {
        "file": filename,
        "target_agent": "human",
        "instructions": f"Unrecognized feedback file: {filename}. Review and resolve manually.",
    }
```

---

### 2.6 Corrupt `STATE.json` silently defaults — HARDENING RECOMMENDATION

**File:** `src/pathly_orchestrator/fsm.py` — `recover_state()`

**Issue:** If `STATE.json` fails to parse (corrupt JSON), the function silently
defaults to the flow's first state and `conv=0`, effectively resetting the feature.
The user has no indication this happened.

**Recommendation:** Add a `"state_recovered_from_corrupt": True` flag to the return
dict when falling back from a parse error. Surface this in the FSM HTTP response so
callers can warn the user:
```python
except (json.JSONDecodeError, OSError):
    state_doc = {}
    corrupted = True
# ... later in the return dict:
"corrupted_state": corrupted,
```

---

## 3. Prioritized Roadmap

| # | Recommendation | Impact | Effort | Area |
|---|---|---|---|---|
| 1 | Agent context bridging (stage brief injection) | High | Medium | Agents/FSM |
| 2 | Rigor level behavioral spec per agent | High | Low | Agents/Skills |
| 3 | Fix `_verify_passed` scan all lines | High | Low | **Python (done)** |
| 4 | Fix `conv_start_sha` stale baseline | High | Low | **Python (done)** |
| 5 | `meet.md` consult auto-injection | Medium | Low | Skills |
| 6 | Feedback TTL visibility in `next_action` | Medium | Low | FSM/Skills |
| 7 | Cross-stage lesson injection (verify wiring) | Medium | Low | Skills |
| 8 | Gate expansion to PLANNING→DESIGNING | Medium | Medium | Flow YAML |
| 9 | Replace `assert` with `raise` | Medium | Low | **Python (done)** |
| 10 | Unrecognized feedback file fallback routing | Medium | Low | Python |
| 11 | Corrupt STATE.json warning flag | Low | Low | Python |
| 12 | Scope gate exempt_prefixes in flow YAML | Low | Medium | Python/YAML |
| 13 | Director routing explanation line | Low | Low | Skills |
| 14 | Debug flow: add REPRODUCING state | Low | Low | Flow YAML |
| 15 | Scout protocol simplification (drop min-2) | Low | Low | Agents |
