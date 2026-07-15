# Pathly — The Path to Production

**Author:** Claude Opus 4.8 (assessment session) · **Date:** 2026-07-15 · **Baseline:** v2.21.1
**Companion to:** [FINDINGS_2026-07-15.md](FINDINGS_2026-07-15.md) (current verified status) and
[SPEC.md](SPEC.md) (the hardening thesis — still correct).

This is the advice you asked for: **where Pathly is, the cycles to run, which apps to build to get a
*proven system*, what's missing from the basic idea, the extra abilities you already have, and the
honest gaps** — with a sequenced plan.

---

## 0. The one goal first (everything else after)

> **A "proven system" is not a feature checklist. It is: Pathly reliably turns a spec into
> working, tested code — across a *diversity* of real apps — with the human only supervising
> (answering questions, adjudicating), not driving each step.**

You already defined the MVP as 6 capabilities. That's the right frame. The finding of this
assessment is that **4 of the 6 are BUILT, 1 is BUILT-with-caveats, 1 is PARTIAL** — so the MVP is
*functionally present*. What's left is **not more features; it is reliability + two exposure gaps +
distribution.** Resist adding new subsystems until the 6 run green end-to-end on real apps. (This is
the SPEC's "consolidation > expansion" thesis, and it's still the right call.)

---

## 1. Where Pathly is — the 6 capabilities, scored + the finishing work

| # | Capability | Status | The finishing work to call it "done" |
|---|---|---|---|
| 1 | **Multiple feature boards + spec each** | ✅ BUILT | None functionally. (Fix `features.py` `full`-tier routing to siblings, minor.) Proven live on invoice-tracker (3 boards). |
| 2 | **Goals → DAG tasks per board** | ✅ BUILT | Add a one-click "create goal + seed DAG" in Studio (today it's create-then-decompose in two steps, or the `goalize` CLI). |
| 3 | **Implement DAG via executors + board-context + code-query** | ✅ BUILT | Make **within-DAG parallelism** real (wire `LaneIsolation` into an executor) *or* commit to serial for v1 and say so. |
| 4 | **Trace agents + full telemetry** | ✅* BUILT | **Empirically confirm cost renders in-app** (one live run). Ship the OTel exporter behind a setting. Validate codex token shape against live output. |
| 5 | **Create flows + control feedback routing** | ⚠️ PARTIAL | Expose `feedback_priority` + `escalation_routing` in the FlowWizard; refresh the wizard's stale default routes to the 5-tag set. |
| 6 | **Create agents/skills + see fragment composition** | ✅ BUILT | Let a **newly-created custom skill** be fragment-mapped in the composition panel (today it's manifest-scoped). |

Net: the spine works. The two visible product gaps are **#5's routing UI** and **#6's custom-skill
composition** — both small, both high-leverage for the "user controls it" story.

---

## 2. Which apps to build — the proof ladder

Run Pathly on a **ladder of real projects that increase in diversity**, not just complexity. The
system is "proven" when you can run rungs 1–4 back-to-back green and do rung 5 at least once. The
*mix* is the point — different languages, app shapes, executors, and greenfield vs. brownfield.

| Rung | App | Exercises | Why it's on the ladder |
|---|---|---|---|
| **1** | **invoice-tracker** (Python CLI, *exists*) | project→3 feature boards→goals→DAG→`single`+`team`; review/test loop | It's already 80% there — a diamond DAG ran to completion. **Finish it:** drive `query-export` (team) to done, then **run its tests and confirm the produced code actually works.** This is your first real proof. |
| **2** | **A pure library** (e.g. a tiny TS/Python util — CSV↔JSON, a date-range helper, a small state machine) | single feature board → goal → `loop` executor → tests green | Greenfield, single language, trivially verifiable (pytest/vitest). Proves the loop end-to-end *unattended*. |
| **3** | **A CLI tool with real I/O + edge cases** (file deduplicator, log summarizer) | more tasks, forces the **review/test + smart-fix-routing** loop | Proves the **unhappy paths**: a real defect gets routed to the owning role, escalation fires, the run terminates cleanly. |
| **4** | **A small full-stack app** (todo API + minimal frontend, or Flask+SQLite) | **multi-feature boards** (data/backend/frontend), the design stage, a bigger DAG | Proves multi-board orchestration + the design flow + cross-feature coordination. |
| **5** | **A feature on an *existing* repo** (brownfield — add to invoice-tracker or an OSS repo) | `/code/query` + board-context on **unfamiliar** code; not-breaking-things | The hardest and most valuable — most real work is brownfield. Proves code-intel + context-retrieval earn their keep. |

**Pass bar for each rung:** produced code compiles + tests pass · human only supervised (answered
questions / adjudicated) · **cost showed a real number** · no orphaned processes · a forced failure
was handled (not hung). Log each run in this board as a goal — dogfood Pathly on the ladder itself.

---

## 3. The cycles to run (repeatable dogfood loop)

You've proven the *happy* path (3 executors succeeded). Production is defined by the paths below. Run
this checklist on each ladder rung, most-risky first:

1. **Failure & recovery** — kill an agent mid-task → DAG marks `failed`, cascade-blocks, run
   *terminates* (not hangs). Force a review to fail 3× → escalation fires (`MAX_FEEDBACK_ROUNDS`),
   doesn't loop. Abort mid-run → PTY dies, **no orphaned CLI** (Windows `killPtyTree`). Kill + restart
   the FSM server mid-run → resumes from the event log.
2. **Renderer-reload survival** — lock the screen / reload Studio mid-run → does the run survive or
   orphan? *This is the reliability gap most likely to bite you daily.*
3. **Cost-in-app (the outstanding empirical proof)** — one full Studio run, confirm DB Explorer shows
   a real number, not `$…`.
4. **Multi-adapter** — a stage on codex + antigravity headless; copilot rejects cleanly.
5. **Clean machine + Windows** — fresh `pip install` → `pathly-setup` → Studio → one full run, nothing
   pre-warmed; no orphaned processes after quit.
6. **Scale** — a 15–20-task DAG + a long single-agent run: board-retrieval relevance as the board
   grows; spawn dual-cap queues without deadlock.

---

## 4. Am I missing basics of Pathly? — yes, three

Your 6 capabilities are the *build-mechanics*. Three things that are equally "the basic idea" and
worth naming explicitly, because they're what make Pathly *Pathly* (not just a task runner):

1. **The human supervisory / governance loop.** The board isn't only a work queue — it's where the
   human **answers agent questions, adjudicates escalations, and approves decisions** *outside* the
   per-step loop. `decision` = continue/block/escalate, `type=escalation` messages, `/comms/answer`,
   the mid-run question flow. A "proven system" must prove the *human-in-the-supervisory-loop* path,
   not just autonomous drain. (Today: real endpoints exist; the UX for answering/adjudicating is the
   thing to exercise on the ladder.)
2. **Adapter-agnostic routing as a first-class capability.** Routing *different stages to different
   CLIs* (`adapter_map` → claude/codex/copilot/antigravity) is the core differentiator vs. single-CLI
   orchestrators — it deserves to be an explicit MVP capability, not folded into "trace agents."
3. **Board context-retrieval + memory as its own capability.** "The board is read back into every
   prompt" is the whole bet. It's a real 4-channel system (governance + referenced/`context_refs` +
   semantic + catalog) plus memory consolidation (`/comms/consolidate`). It's not free — its
   *relevance at scale* is a capability to prove (rung 6 of §3), not assume.

---

## 5. Extra abilities you already have (lean into these)

Built and working, beyond the 6 — cheap wins to surface:

- **Code intelligence** — `/code/query` (graph + Serena LSP, `backend:"both"`), self-healing index,
  composed into build/loop/team agents as the `code-query` fragment. A real moat; today the
  *auto-injected* code block is off-by-default (agents can still pull it on demand).
- **Memory consolidation** — near-dup dedup + a reflection pass (`/comms/consolidate`).
- **Context-retrieval tiers** — manifest → section hydration → semantic search → catalog.
- **Determinism → run replay** — the FSM is reconstructable from the event log; expose it as a
  debugging/replay tool (SPEC Phase 5).
- **Spawn scheduler** — dual-cap concurrency gate + rate-limit backoff; already the single source of
  engine liveness feeding the Monitor + dock.
- **Live telemetry surfaces** — EngineBoard, DB Explorer roll-ups, per-flow cost badges, OTLP-shaped
  spans (just not exported over the wire yet).

---

## 6. The honest gaps (in priority order)

**Reliability (do first — this is the actual blocker):**
1. Renderer-reload orphans runs (partial mitigation only).
2. Empirical cost-in-app unconfirmed (wiring verified, live render not).
3. No standalone / CI drain — the supervisor needs Studio as the PTY host.
4. Within-DAG parallelism is serial-only (`LaneIsolation` exists but unwired; `WorktreeIsolation` is P3).

**Product exposure (small, high-leverage):**
5. Feedback-routing priority/escalation are YAML-only; wizard defaults are pre-smart-fix.
6. New custom skills can't be fragment-mapped in-panel.
7. Core skill/agent edits need `pathly-setup --repair` to take effect (not in-app).

**Trust / drift (keeps regressing):**
8. No CI gates — 400-line rule now broken by **14 files**; no doc-structure / dash-safety / adapter-parity gates.
9. Board-scope leak (eval/board_run → wrong board), diagnosed not fixed.

**Distribution (pure ops, gates public launch):**
10. Installer unsigned (plumbing exists; certs not provisioned).
11. Non-claude cost is estimated; OTel export dormant.

---

## 7. Sequenced plan

**P0 — prove the ONE loop on real apps (the keystone).**
- Finish invoice-tracker (rung 1); confirm the produced code passes its tests.
- Close the **empirical cost-in-app** proof (one live run showing a real number).
- Run the **unhappy-path cycle** (§3) on rungs 1–2; fix what orphans/hangs — especially
  **renderer-reload survival** (persist+rehydrate, the deferred SSE-replay layer).
- Exit gate: rungs 1–2 run green, unattended-supervised, 3× each.

**P1 — close the two product-exposure gaps + stop the drift.**
- Expose `feedback_priority` + `escalation_routing` in the FlowWizard; refresh its default routes.
- Let a newly-created custom skill be fragment-mapped in the composition panel.
- Add the CI gates the SPEC already specifies (400-line, doc-structure, dash-safety, adapter-parity).

**P2 — scope + distribution.**
- Decide serial-vs-parallel for v1 (wire `LaneIsolation`, or commit to serial and message it).
- Provision installer signing (Windows EV + Apple notarization).
- Ship the OTel exporter behind a setting; validate codex token accuracy.
- Then run rungs 3–5 of the ladder; a green rung 5 (brownfield) is the "proven system" milestone.

**Frontier stays parked** (differ, broad code-intel expansion, parallel-fleet) until P0–P1 are green —
re-admit each behind its own smoke test. That discipline is the difference between "converges to
production" and "widens the untested surface" (the exact pattern that produced the earlier
regressions).

---

*Bottom line: Pathly is one reliability push — not a feature push — from a proven, supervised
code-building system. Prove it on the app ladder, close the two exposure gaps, sign the installer.*
