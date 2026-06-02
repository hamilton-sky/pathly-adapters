# Edge Cases — pathly-observability

## EC-01: /record_phase called for a feature with no plans directory

**Scenario:** The endpoint is called with `feature: "new-feature"` but
`pathly/plans/new-feature/` does not exist.

**Expected behavior:** The endpoint returns HTTP 400 with
`{"error": "feature directory not found: pathly/plans/new-feature/"}`.
It does NOT create the directory or the file. The caller is responsible for
ensuring the feature directory exists before logging phase events.

**Rationale:** Auto-creating directories would silently mask typos in feature names and
pollute the plans directory with phantom features.

---

## EC-02: /record_phase called when EVENTS.jsonl exists but is corrupt

**Scenario:** `pathly/plans/my-feature/EVENTS.jsonl` exists but contains invalid JSON
(e.g., a partial write from a previous crash).

**Expected behavior:** The endpoint appends a new JSON line regardless. JSONL format
allows each line to be independently valid. The corrupt line remains in the file. The
endpoint returns HTTP 200. It is the reader's responsibility to skip invalid lines.

**Rationale:** Appending is safe with JSONL. Aborting on corrupt history would block all
future logging for that feature.

---

## EC-03: PHASE_DONE written without a preceding PHASE_START

**Scenario:** An agent calls `log-phase PHASE_DONE implement` without having called
`log-phase PHASE_START implement` first (e.g., the server was restarted mid-session).

**Expected behavior:** The endpoint accepts and appends the PHASE_DONE event without error.
It does NOT enforce ordering or validate that a matching PHASE_START exists.

**Rationale:** Strict ordering would make phase logging fragile under network interruption
and server restarts. Consumers of EVENTS.jsonl must handle unpaired events gracefully.

---

## EC-04: scope_gate.exempt_prefixes is present but empty in flow YAML

**Scenario:** The flow YAML has `scope_gate: {exempt_prefixes: []}` (empty list).

**Expected behavior:** `_is_exempt()` behaves exactly as before — only the hardcoded
defaults (`pathly/plans/` and `.tsbuildinfo`) are active. The empty list does not error
or override the hardcoded defaults.

---

## EC-05: HTTP server is not running when a skill calls log-phase

**Scenario:** A builder agent is running but the Pathly HTTP server (port 8765) is not up.
The skill calls `log-phase PHASE_START analyze` which executes a curl command.

**Expected behavior:** The curl command fails silently (non-zero exit, output discarded).
The skill continues execution. Phase logging is best-effort and must never block skill work.

**Implementation note:** The log-phase utility skill must include `|| true` or equivalent
to prevent skill abort on curl failure. Document this in log-phase.md.

---

## EC-06: Two agents log phases for the same feature simultaneously

**Scenario:** Builder and reviewer are running concurrently (unlikely but possible) and
both call `/record_phase` at the same time, causing a concurrent file write.

**Expected behavior:** Both writes are appended. Because JSONL appends are atomic at the
OS level for small writes, the lines do not interleave. In the worst case one write is
lost. No error is surfaced. This is an acceptable trade-off for simplicity.

**Out of scope:** File locking and write queuing are not in scope for this feature. If
concurrent writes become a problem, it is a separate feature.

---

## EC-07: rigor_contract table references a rigor level the FSM never sends

**Scenario:** The rigor_contract table in an agent file has a `nano` row, but the project
uses only `standard` and `strict`. An agent reads the nano row and incorrectly applies it.

**Expected behavior:** The agent reads the `rigor` field from the FSM agent_hint and looks
up only that row. The presence of other rows in the table does not affect behavior.

**Acceptance:** Not a code change — this is a documentation clarity note. The rigor_contract
table format must include a note: "Read only the row matching the current rigor level."

---

## EC-08: pathly-setup fails mid-propagation for one adapter

**Scenario:** `pathly-setup claude --apply` succeeds but `pathly-setup codex --apply` fails
(e.g., codex install directory does not exist on this machine).

**Expected behavior:** Conv 4 builder reports the failure clearly. The claude adapter is
deployed. The codex failure is noted. The conversation is marked partially done in PROGRESS.md.

**Acceptance:** This is not a blocker for the feature — codex is optional on machines where
it is not installed. The builder must not silently swallow the error.

---

## EC-09: Agent file has no "What NOT to do" section to anchor rigor_contract placement

**Scenario:** An agent file does not have a `## What NOT to do` section, so the placement
rule ("immediately before What NOT to do") cannot be applied.

**Expected behavior:** The builder places the `## Rigor contract` section as the
second-to-last section in the file (before whatever is currently last). If the file has
only one section, it is added at the end.

---

## EC-10: conv field is omitted from /record_phase request

**Scenario:** A skill calls `/record_phase` without a `conv` field (older skill version or
standalone call).

**Expected behavior:** The endpoint accepts the request. The appended event line does not
include a `conv` field (not written as null). All other fields are written normally.
HTTP 200 returned.
