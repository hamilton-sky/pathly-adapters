# Full-Flow Readiness — Click Start → DONE

Code-verified end-to-end assessment of the Pathly runner pipeline.
Date: 2026-06-15 · Scope: Studio → /runner/start → supervisor → FSM → agent PTY → DONE, plus comms board.

Every claim below is anchored to `file:line`. Where the source maps disagreed or a
finding was load-bearing, I re-read the code directly — those checks are called out.

---

## 1. Verdict

**Yes — a user can click Start today and drive a feature from STORM to DONE, in the
default (non-interactive, early-advance-on) configuration, provided the Claude CLI is
on PATH and the feature already has a topic set.** All six seams of the critical path
are implemented and wired: the Start button POSTs `/runner/start`
(`FlowControlBar.tsx:65-68`), the supervisor spawns a daemon loop
(`supervisor/api.py:64-70`), the loop polls `/next_action`, spawns a visible PTY via
`TERMINAL_SPAWN` (`terminal.py:200-214`), waits for the result, and calls
`/complete_stage` to advance (`orchestrator.py:484-487`); the FSM walks all 8 states to
a terminal `{"done": True}` (`fsm_ops.py:635-636, 812-813`); and the full agent prompt
is assembled and delivered in-argv with no CLI-side file read
(`fsm_ops.py:169-230`, `adapters.yaml:1-3`).

**There is no missing or stubbed code on the base path.** The previously-reported
"early-advance reconciliation hang" is **not a live blocker** — see §3, item 1: the
reconciliation window runs in a *daemon* thread spawned at `terminal.py:310-316`
**after** the supervisor has already returned `result_for_fsm` at `terminal.py:317`, so
it never blocks the loop. The remaining risks are configuration/environment hazards
(CLI on PATH, interactive-mode flag coupling, headless `decide`/human escalation), not
absent functionality. The single biggest *practical* risk to a first clean demo is
**environment**: the Claude CLI must be resolvable from the PTY's spawned shell, and the
feature must already have a topic (Start is disabled otherwise by design).

---

## 2. End-to-end status table

| Seam | Status | Evidence (file:line) | Note |
|---|---|---|---|
| Studio → `/runner/start` | **WORKS** | `FlowControlBar.tsx:65-68` → `lib/config.ts:17-22` → `blueprints/runner.py:18-99` | Click → `apiFetch('/runner/start', POST)` with validated body; backend calls `start_run(...)`. |
| Supervisor thread spawn | **WORKS** | `supervisor/api.py:64-70` | `start_run` creates `RunnerState`, spawns daemon `_loop` thread. |
| Supervisor loop (poll/advance) | **WORKS** | `orchestrator.py:230-297, 376-389, 484-487` | Boundary checks → `next_action` → terminal invoke → `_resolve_stage_supervised`. |
| FSM `/next_action` | **WORKS** | `fsm_ops.py:507-650` | `recover_state` → `build_prompt` → `agent_hint`; `DONE` short-circuits to `{"done": True}` (635-636). |
| FSM `/complete_stage` | **WORKS** | `fsm_ops.py:653-828` | `evaluate_transition_rules` → gates → actions → `write_state` → `append_event`. |
| Agent prompt assembly | **WORKS** | `fsm_ops.py:169-230` | Role/skill + var injection + task ctx + pipeline history + comms board, all in one string. |
| Prompt → argv (no file read) | **WORKS** | `runner/argv.py:47-64`, `adapters.py:20-73`, `adapters.yaml:1-3` | Full prompt embedded in `-p` argument; CLI reads nothing from disk. |
| `TERMINAL_SPAWN` → PTY | **WORKS** | `terminal.py:200-214` → `useHQ.tsx:278-305` → `ipc/terminal.ts:221-400` | SSE payload → `terminal:spawn(argv)` → `node-pty` spawns native process. |
| Windows long-prompt argv | **WORKS** | `ipc/terminal.ts:160-204` | Temp `.ps1` here-string for prompts >32 KB (correct; supersedes the stale `-EncodedCommand` note in the FSM CLAUDE.md). |
| PTY exit → `/runner/terminal/result` | **WORKS** | `ipc/terminal.ts:357-397` → `blueprints/runner.py:122-199` | POSTs exit code + stdout tail; backend enriches with `AGENT_DONE.summary` from DB. |
| Result → FSM continue | **WORKS** | `terminal.py:255-346`, `orchestrator.py:484-523` | `wait_result_or_agent_done` / `wait_pty_result` → `complete_stage` → `next_state` loop. |
| SSE → Studio store | **WORKS** | `streams.py:68-106`, `sse.py:127-137` → `useHQ.tsx:220-380` | Queue-based broadcast; handles `STAGE_CHANGE`/`COST_UPDATE`/`TERMINAL_SPAWN`/etc. |
| Session continuity + cost | **WORKS** | `orchestrator.py:323-359, 463-471` | Same-adapter session reuse; `cost_usd_so_far` accumulation; `COST_UPDATE` broadcast. |
| Early-advance reconciliation | **WORKS (non-blocking)** | `terminal.py:308-317`, `registry.py:58-73` | Daemon recon thread starts *after* the return; never blocks the loop. See §3.1. |
| Comms board (alongside flow) | **WORKS** | `fsm_ops.py:211-229`, `comms_context.py:89-276`, `blueprints/comms.py` (15 routes) | Board context injected when non-empty; governance + advisory channels. P1 landed. |
| Interactive mode | **PARTIAL** | `terminal.py:178-185` | Hard-coupled to `early_advance`; raises `RuntimeError` if `PATHLY_RUNNER_EARLY_ADVANCE=0`. Not on the default demo path. |
| Headless `decide` transitions | **PARTIAL** | `runner/cli.py:~29` | Raises "interactive decision required but running headless." `team.flow.yaml` has no `decide` rule, so default flow is unaffected. |
| Human checkpoints (headless) | **PARTIAL** | `orchestrator.py:139-152` | `target == "human"` → `_set_status("error")`. By design; only triggered if a feedback file routes to human. |
| FSM state-schema validation | **PARTIAL** | `eventlog.py:138-146`, `fsm/state.py:43-44` | `VALID_STATES` from `state.schema.json` ≠ `team.flow.yaml` states. Latent only — see §5. |

No seam is **BROKEN** or **MISSING** on the base path.

---

## 3. Critical-path blockers, ranked

Ordered by likelihood × impact of breaking a first clean "click Start → DONE" run.

### 1. test_early_advance hang — TEST-ONLY harness risk, NOT a live bug · fix size: S (or none)
- **What the source map claimed:** a daemon `_reconciliation_window` deadlocks live runs
  for up to 1800s when a PTY crashes without POSTing a result.
- **What the code actually shows:** in the non-interactive early-advance path,
  `_reconciliation_window` is launched as a **daemon thread** at `terminal.py:310-316`,
  and the function **returns `result_for_fsm` at `terminal.py:317` immediately after**.
  The supervisor loop is therefore *not* blocked by reconciliation — it advances. The
  recon thread blocks only itself (`registry.py:58-60`, `wait_pty_result(timeout=600)`),
  holding one `TerminalRun` object for ≤600s before writing `STAGE_RECONCILIATION_FAILURE`
  and calling `drop_run` (`terminal.py:142-158`). Worst case is a leaked-for-≤10-min
  object and a missed billing patch — **not** a stalled pipeline.
- **The test itself does not hang as written.** `test_early_advance_with_billing_reconciliation`
  (`tests/test_supervisor.py:693-767`) patches `_reconciliation_window` with `fake_recon`,
  which calls `run_.mark_pty_result({...})` *before* invoking the original with
  `timeout=0.2` (`test_supervisor.py:719-723`). The PTY result is pre-satisfied, so
  `wait_pty_result` returns immediately. **Verdict: real concurrency *smell* (daemon
  thread + 600s wait), but not a live flow blocker and not a hanging test in current
  source.** If a hang was observed, check for an environment where the
  `_reconciliation_window` patch is bypassed or `mark_pty_result` is not reached.
- **Optional hardening (S):** lower the recon `timeout` default (`terminal.py:111`, 600s)
  and/or make `drop_run` idempotent on supervisor shutdown so leaked runs are reaped on
  abort.

### 2. Claude CLI must be resolvable from the spawned PTY shell · fix size: S
- **What's wrong:** `adapters.yaml:1-3` emits argv `["claude", "-p", ...]`; the PTY spawns
  via `node-pty` with `env: process.env` (`ipc/terminal.ts` spawn block). If `claude` is
  not on the PATH that Electron inherited, the PTY exits non-zero and the supervisor
  raises `terminal_exit_nonzero` (`terminal.py:324-327, 342-345`) — the run errors at
  stage 1.
- **Why it blocks:** this is the most common real-world first-run failure and is invisible
  until a stage actually spawns. The FSM server itself is spawned with `env: {...process.env}`
  (`index.ts:110-113`), so PATH must be correct in the Electron parent process.
- **Fix:** verify `claude --version` resolves in the same shell Electron launches from
  before the demo; document the PATH requirement.

### 3. Interactive mode crashes if early-advance is disabled · fix size: S
- **What's wrong:** `terminal.py:178-185` raises `RuntimeError("Interactive mode requires
  PATHLY_RUNNER_EARLY_ADVANCE=1")` when `state.interactive` is true and
  `feature_flags.early_advance` is false.
- **Why it blocks:** only if the user starts in interactive mode *and* has explicitly set
  `PATHLY_RUNNER_EARLY_ADVANCE=0`. Both default safely (early_advance defaults True per
  `feature_flags.py:28-53`), so the default demo path is clear. Listed because the coupling
  is implicit and the failure is a hard crash, not a graceful degrade.
- **Fix:** for the demo, leave interactive off (default) or ensure the flag stays default-on.

### 4. Headless `decide` transitions raise · fix size: M (only if a decide flow is used)
- **What's wrong:** `runner/cli.py:~29` raises when a `decide`-type transition rule is hit
  with no interactive channel.
- **Why it blocks:** `team.flow.yaml` (the default flow) contains **no `decide` rule** — its
  branches are `on_content`/`on_artifact`/`on_state_counter`/default — so the default demo
  never hits this. It only blocks custom flows that add a decision point.
- **Fix (M):** route `decide` through the runner decision SSE (`/runner/decision` already
  exists) instead of raising, so headless can auto-pick the default option.

### 5. Human-routed feedback escalates to error in headless · fix size: M
- **What's wrong:** `orchestrator.py:139-152` sets status `error` when a feedback file routes
  to `target == "human"`.
- **Why it blocks:** only triggered if a gate/feedback writes a human-targeted file. The
  default happy-path run (no failures) never produces one; a REVIEW/TEST failure that routes
  to `architect`/`builder` loops back fine. A human-only escalation hard-stops the run.
- **Fix (M):** surface a `DECISION_MENU`/question to Studio and wait, rather than erroring.

### 6. (Latent, not on critical path) state-schema mismatch · fix size: M — see §5.

---

## 4. Already works (credit where due)

These seams are genuinely wired end-to-end and verified:

- **FSM server lifecycle.** App launch health-checks port 8765, shuts down stale instances,
  force-kills as a fallback, and spawns a fresh Python server; killed on quit
  (`index.ts:109-120, 164-184`).
- **Start → supervisor.** Validated POST → `start_run` → daemon `_loop`
  (`runner.py:18-99`, `api.py:32-70`).
- **Full FSM walk to DONE.** All 8 states (STORMING→PLANNING→DESIGNING→BUILDING→REVIEWING→
  TESTING→RETRO→DONE) are reachable with no dead ends; terminal state returns `{"done": True}`
  (`team.flow.yaml`, `fsm_ops.py:635-636, 812-813`).
- **Dual-source result merge.** `cost_usd`/`session_id` from `--output-format=json` stdout;
  semantic `result` from `AGENT_DONE.summary` in the central DB, immune to PTY buffer
  truncation (`runner.py:122-199`).
- **State persistence round-trip.** Atomic STATE.json write (`.tmp`→rename + fsync) plus
  SQLite upsert with Windows path normalization; split-brain and `convs_done` overwrite bugs
  fixed (`eventlog.py:114-166`, `fsm_state.py:16-44`, commit `b0c150c4`).
- **Prompt delivery with zero CLI file reads.** Entire agent context is embedded in the `-p`
  argv (`argv.py:47-64`, `adapters.py:20-73`).
- **SSE pipeline.** Queue-based broadcast with 25s heartbeat and exponential-backoff reconnect;
  Studio handles every event type into `runnerStore` (`streams.py:68-106`, `useHQ.tsx:220-380`).
- **Session continuity + cost accumulation.** Same-adapter session reuse and per-stage cost
  roll-up with `COST_UPDATE` broadcast (`orchestrator.py:323-359, 463-481`).
- **Comms board (P1).** 15 `/comms/*` routes plus board-context injection into every agent
  prompt when non-empty (`blueprints/comms.py`, `comms_context.py:89-276`, `fsm_ops.py:211-229`).
- **Windows long-prompt safety.** Temp `.ps1` here-string handles prompts past the 32 KB
  `CreateProcess` ceiling (`ipc/terminal.ts:160-204`).

---

## 5. Adjacent / not blocking the base flow

- **State-schema mismatch (latent).** `eventlog.write_state` validates `current` against
  `VALID_STATES` derived from `state.schema.json` (`fsm/state.py:43-44`), whose state set
  (IDLE, DISCOVERING, CONSULT_OPEN, …) differs from `team.flow.yaml` (STORMING, PLANNING, …).
  When a `flow` arg is passed, `valid_states(flow)` is used instead
  (`eventlog.py:138-146`), so the live `complete_stage` path validates against the flow, not
  the schema — that is why the default flow is unaffected today. Risk only materializes for a
  flow whose states aren't passed through, or a direct STATE.json write. **Fix (M):** regenerate
  `state.schema.json` from the canonical flows, or always thread `flow` into `write_state`.
- **SSE feature flag.** `streams.py:140-141` returns 503 if `PATHLY_FF_SSE_STREAMING=false`.
  Defaults True; disabling only degrades live UI updates, not pipeline execution.
- **Empty `adapter_map` → fallback "claude".** `fsm_ops.py:343-346` returns `""`, but
  `build_prompt`/argv default to `claude`. Harmless with the default config.
- **Comms board polish (P1.5)** and **DAG scheduler (P2).** Improve multi-agent coordination
  and parallel task fan-out; neither is required for the linear STORM→DONE base flow.
- **Webhook notifier disabled by default** (`webhook.py:36`) — telemetry only.

---

## 6. Shortest path to a working demo

### Must-fix (gate the first clean run)
1. **Confirm the Claude CLI resolves on PATH** in the shell Electron inherits
   (`claude --version`). This is the highest-probability real failure (§3.2). — env, minutes.
2. **Set a topic before clicking Start.** Start is disabled with no active feature by design
   (`FlowControlBar.tsx:49-55`); run `/pathly go` (or set the topic in Studio) first. — UX, seconds.
3. **Keep defaults: early-advance ON, interactive OFF.** Avoids the interactive↔flag crash
   (§3.3) and exercises the verified non-interactive path. — env, seconds.

### Should-verify (de-risk, not strictly blocking)
4. **Use the default `team` flow** (no `decide` rule, no human-only feedback routing) so §3.4
   and §3.5 cannot trigger on the happy path.
5. **Smoke-run a single stage** (STORMING) and confirm the chain: `TERMINAL_SPAWN` →
   PTY opens → `AGENT_DONE` in EVENTS.jsonl → `STATE_TRANSITION` to PLANNING. If this one
   stage works, the loop is identical for every subsequent stage.

### Nice-to-have (post-demo hardening)
6. Lower `_reconciliation_window` timeout and reap leaked runs on abort (§3.1).
7. Make headless `decide` auto-select the default option instead of raising (§3.4).
8. Convert human-feedback escalation into a Studio decision prompt rather than `error` (§3.5).
9. Regenerate `state.schema.json` from canonical flows to close the latent mismatch (§5).

**Bottom line:** the wiring is done. With the Claude CLI on PATH, a topic set, and default
flags, "click Start → DONE" should run today on the `team` flow. The remaining items harden
edge cases (interactive mode, custom decide flows, human checkpoints, billing reconciliation,
schema validation) — none of which sit on the default linear path.
