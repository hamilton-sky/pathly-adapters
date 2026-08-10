# Headless CLI Control Plane — next-increment requirements

**Branch:** `feat/headless-cli-control-plane` (off `master` @ `ed8c61ef`, the landed unified-control-plane feature)
**Parent feature:** `unified-control-plane`
**One-line thesis:** the **Pipeline** section becomes the *single* place to observe AND control **every headless CLI spawn** in the app; the **board** goes back to being **governance-only** (goals / decisions / discoveries / artifacts / DAG tasks) — no more agent progress noise.

> Scope guard (unchanged from prior sessions): `pathly-run`, interactive chat, and local models (`aiRouter.runModel`) are a **separate system, out of scope** here.

---

## The 8 requirements (as stated)

1. **Single chokepoint** — verify every headless CLI spawn flows through one place so it's trackable.
2. **Logs → Pipeline** — every headless CLI spawn logs to the Pipeline section.
3. **No board progress** — headless spawns post progress ONLY to the Pipeline, not the board.
4. **Mid-phase logs in Pipeline** — a spawn's mid-phase logs are visible live in the Pipeline.
5. **FSM/team control from Pipeline** — team (FSM) runs are controlled from the Pipeline section.
6. **Gate-guard before execute** — every headless spawn shows the gate-guard preview component before executing (the pattern already used elsewhere in the app).
7. **Full-page launcher** — the New-run surface is a full PAGE (not a modal) that shows the user the full functionality/observability of the agent flow when a team or single agent is selected.
8. **Remove board mid-phase component** — headless spawns no longer post mid-phase logs to the board; the board component that renders them is removed.

---

## Status vs. what `unified-control-plane` already shipped

| # | Requirement | Status | Where it stands |
|---|---|---|---|
| 1 | Single chokepoint | 🟡 **PARTIAL / audit** | Supervisor spawns already funnel through ONE issue point (`supervisor/terminal.py::_run_stage_via_terminal` → issues `run_id`, writes `run_history` identity + `run_log`) and ONE settle point (`POST /runner/terminal/result`, the billing gate). Renderer one-shots take a **second door** (`POST /db/invocation`). Both now share the *same* server parser (`runner/output.py::parse_result`), and the Studio `terminal.ts` dual-cap scheduler is the single **process** chokepoint all PTYs cross. So it's *nearly* one place — Task 1 is to **audit + prove** every in-scope spawn issues a `run_id` and lands in `run_history`, and decide whether to collapse the two telemetry doors into one "spawn-record" writer. |
| 2 | Logs → Pipeline | 🟢 **MOSTLY DONE** | `run_history` + `run_log` (prompt+stdout) + `agent_invocations` (cost/tokens) all back `GET /runs` and `GET /runs/<id>` → the RunDetail page. One-shots write their own `run_history` row. Remaining: confirm no in-scope spawn is missing a row. |
| 3 | No board progress | 🟡 **CHANGE** | Progress narration (`record-phase`) already writes to `fsm_events` (Pipeline), NOT the board. But **PHASE markers** currently ARE posted to the board as `type='phase'` messages. This req evicts those. **Governance posts (decisions/discoveries/artifacts) STAY** — they *are* the board's job. |
| 4 | Mid-phase logs in Pipeline | 🟢 **DONE (supervisor)** | RunDetail **Phases** tab (live PHASE timeline) + **Logs** tab (stdout, collapsible) + live refresh via `GET /events/runs?run_id=`. One-shots are single-shot (stdout only, no phases). |
| 5 | FSM/team control from Pipeline | 🟢 **DONE** | `RunControls` on RunDetail: Stop (any active) + Pause/Resume/Advance/Reroute/Retry (flow runs), run_id-addressed via `POST /runs/<id>/<action>`. Remaining: E2E-verify against a live team run. |
| 6 | Gate-guard before execute | 🟡 **PARTIAL** | `FlowGatePreview` (run-agnostic gate: stage stepper + per-stage prompt/Sections) already gates **board Run→Flow**, **team goal Run**, and the **consultation** decomposers. It does NOT gate: the **New-run launcher**, **single/loop goal runs** (explicitly ungated), or **renderer one-shots**. |
| 7 | Full-page launcher | 🔴 **NEW** | Today New-run is a modal (`NewRunModal`). Req wants a full page that *previews the agent flow*: team → the FSM stage pipeline the agents will traverse; single → the agent + skill + board-context it will run with. |
| 8 | Remove board mid-phase component | 🔴 **NEW** (pairs with #3) | Remove the Command Center surface that renders phase/progress posts; board = governance-only. |

**Net:** ~5 of 8 are done or nearly so (the unified-control-plane spine). The genuinely **new** work is **#6 (gate everywhere)**, **#7 (full-page launcher)**, and **#3+#8 (evict phase posts from the board)**.

---

## Req 9 — additions & corrections (my recommendations)

- **A. The headless ↔ gate tension (about #6).** Pathly's whole premise is *no human in the per-step loop* for headless runs. A gate-guard before **every** spawn — including each auto-advanced FSM stage or each drained DAG task — would break that. **Recommendation:** the gate fires for **user-initiated launches** (New-run, board Run) — i.e. gate the *launch*, not each internal step. Auto-advance stages and headless drains stay ungated once launched. (Optionally: a per-run "step-through" debug toggle that re-enables per-stage gating on demand.)
- **B. Keep governance on the board (sharpen #3).** #3/#8 remove **progress + PHASE** posts, NOT decisions/discoveries/artifacts/escalations/questions/DAG tasks — those are the board's reason to exist and are read back into every agent prompt as context. Worth stating explicitly so a builder doesn't strip the wrong thing.
- **C. Collapse the two telemetry doors (finishes #1).** `POST /runner/terminal/result` (supervisor) and `POST /db/invocation` (one-shots) should converge on one "spawn-record" concept so "one place to track" is literally true, not just parser-shared.
- **D. Reuse the gate as the launcher (merge #6 + #7).** The full-page launcher (#7) and the gate-guard (#6) are the *same idea* — preview-before-run. Build #7 **on top of** `FlowGatePreview`'s existing stage-preview rather than a second flow-preview engine. One component, two entry sizes (full-page for launch, inline for gate).
- **E. Global kill-switch (extends #5).** A Pipeline-level "stop all active runs" panic control — natural companion to per-run control.
- **F. Unify the two spawn-observability surfaces.** The floating `CliMonitorBar` dock and the Pipeline Runs list both show spawns today. Decide: one canonical surface, or a clear dock=glance / Pipeline=control split.
- **G. Renderer one-shots & the gate.** Editor AI actions (Split/Analyze/Diagram/Comment) are synchronous and user-initiated. They should stay **tracked** (#1/#2) but likely get a *lightweight* confirm, not the full-page flow — decide their gate treatment explicitly.
- **H. Verify nothing reads phase posts back.** Before evicting PHASE posts (#3/#8), confirm no prompt path (`retrieve_board_context`) depends on them as context. If any does, that signal must come from the Pipeline channel instead.

---

## Req 11 — do the requirements make sense?

**Yes — they're the coherent completion of the unified-control-plane thesis**, not a new direction: *Pipeline = the single observe+control plane for headless spawning; board = governance-only.* The codebase already leans this way (`studio/CLAUDE.md`: "Logging is deliberately NOT a setting … Pipeline = operational plane, board = context governance").

Two clarifications keep it clean: **(1)** gate the *launch*, not every headless step (A), and **(2)** "no board progress" means evict PHASE/progress, keep decisions/discoveries (B).

**Suggested next step:** decompose these into a task-DAG on the board (as last increment) and drain with builders — starting with the **#1 audit** (it decides how much of the rest is verify-vs-build), then **#3+#8** (board eviction), then the larger **#7 launcher** reusing **#6**'s gate.
