# Unified Control Plane — RESEARCH (external, lightweight pass)

**Stage:** Research (consultation, stage 3) · **Date:** 2026-07-24 · **Author:** web-researcher
· **Scope:** 3 external questions only (internal refactor — design is mostly fixed by our own code).
All findings are external + unverified: cited, not asserted. Treat as advisory input to design/plan.

---

## 1. Pipeline observability UX (Azure DevOps Pipelines / GitHub Actions)

How mature pipeline UIs structure the run view, and what's worth copying for the Studio `Pipelines/` pane.

- **Strict drill-down hierarchy: run-list → run summary → stages/jobs pane → steps → per-step log.**
  Azure DevOps defaults the run list to a **"Recent"** view with an **"All"** toggle; selecting a run opens a
  summary, and a **Stages/Jobs** overview pane lets you drill into a job's steps. This is exactly our
  `RunList → RunDetail(Stages) → per-stage LogsTab` shape — the design already matches the convention. [1]
- **One surface serves both live and terminal state.** The run summary "view the status of your run, **both
  while it is running and when it is complete**" — there is no separate "monitor" vs "history" screen. This
  validates folding today's Monitor-RECENT semantics into the one pane. **Live logs stream once the agent is
  allocated** ("you'll start seeing the live logs of the build"). [1]
- **Escape hatches on the per-step log:** a **"raw log" / "download logs"** action and a **timestamps toggle**
  live in a per-step *More actions* menu. Our LogsTab shows a PTY *tail* (may be truncated), so an explicit
  "this is a tail" label + a raw/download affordance is the honest analogue. [1]
- **Status vocabulary + run-level actions.** Runs are cancel-while-running / **re-run (Run new)** when done,
  with retain/delete tied to a **retention policy**; stage/job status reads at a glance. Adopt the badge set
  **queued / running / succeeded / failed / skipped / canceled** for the Stages tab. (Cancel/re-run are
  display-only in our read-only P0 — real controls are P3.) [1]

→ **Implication for our MVP:** the P0 pane's structure is already idiomatic; the cheap wins for the *designer*
are a queued/running/succeeded/failed/canceled badge set, a "PTY tail (may be truncated)" label, and a
raw-log/download escape hatch in LogsTab — no new backend.

## 2. SSE fan-out / multiplexing (for P1 `_broadcast_run_event` / `GET /events/runs`)

Patterns + pitfalls for a single run-scoped feed that many clients filter.

- **Give every event a monotonic id and honor `Last-Event-ID` on reconnect — the #1 cited pitfall.** "Skip the
  `id` field and replay silently breaks; always use monotonic sequence numbers from your event store." On a
  network blip the browser auto-sends `Last-Event-ID` and the server should replay from that seq. We already
  own a monotonic store key — **`fsm_events.seq`** — so stamp it as the SSE event id and resume from it. [2][3]
- **Per-client queues + non-blocking writes so one slow client can't stall the fan-out.** The idiomatic
  broadcast is "every subscriber receives every event and locally drops the ones it doesn't want"; a slow
  client must never block the producer — use non-blocking enqueue and drop/pause on backpressure. Our planned
  `_run_clients: list[Queue]` is right; make each enqueue **bounded + non-blocking** (drop-oldest) so a stalled
  EventSource can't back up the broadcaster. [2][4]
- **Server-side `?run_id=` filter (already in the SPEC) is correct** — don't ship the firehose to every client.
  Also ensure the SSE generator isn't response-buffered (the existing `/events/spawn` generator already handles
  this; proxy/gateway buffering is the most common deploy-time breakage, low risk on localhost). [2][4]

→ **Implication for our MVP:** in P1, reuse `fsm_events.seq` as the SSE `id:` and implement `Last-Event-ID`
replay in `GET /events/runs` — this makes the "DB on mount, SSE overlay" reload invariant robust instead of
best-effort. Use bounded, non-blocking per-client queues.

## 3. Replayable run-record / event-sourcing (persisting full stdout + prompts)

Standard caveats for a durable debug transcript (`run_log` = prompt + board-context + stdin + stdout).

- **Unbounded growth needs an explicit retention/prune policy.** Persisting full per-stage stdout + prompts for
  every run grows without bound (the PO already flagged this; the human chose "full untruncated" but deferred
  retention). Mature pipelines tie logs to a **retention policy** with automated deletion. [1][5]
- **Prompts + stdout are a hidden-PII / secret sink.** "PII leaking into debug logs through traces is the most
  common source of hidden PII exposure"; the cited anti-pattern is *store-now-redact-later*, which leaves
  unredacted data in the DB, **backups, and search indices**. Our composed prompt can embed API keys / tokens /
  absolute paths pulled into context, and `run_log` is a *new* durable sink that backups now capture. [6][7]
- **Keep the record non-authoritative so pruning is always safe.** Event-sourcing's "right to be forgotten"
  problem (full history resists targeted deletion; answered by tombstone/crypto-shred) is avoided entirely if
  the sink is *droppable*. Our design already makes `run_log` a debug/display sink with billing authoritative
  in `agent_invocations` — so a prune (by age or per-project row cap) is lossless. [8]

→ **Implication for our MVP:** add a **bounded retention/prune** for `run_log` (age window or per-project cap)
and keep it strictly non-authoritative (already true), so pruning never loses billing. Flag that `prompt_sent`
may contain secrets — LogsTab should not be exported/shared blindly, and a future redaction pass is a known
follow-on (out of MVP).

---

### Sources
1. Azure Pipelines — run list / summary / stages-jobs pane / live logs / raw-log + timestamps / retention:
   <https://learn.microsoft.com/en-us/azure/devops/pipelines/create-first-pipeline>
2. Node.js SSE 2026 production guide (ids, Last-Event-ID, backpressure, proxy buffering):
   <https://www.hirenodejs.com/blog/nodejs-server-sent-events-sse-2026>
3. MVP Factory — Last-Event-ID recovery on reconnect: <https://mvpfactory.io/blog/server-sent-events-as-your-mobile-real-time-layer-automatic-reconnection-last/>
4. Galaxy Project — SSE fan-out (every worker gets every event, drops non-local): <https://docs.galaxyproject.org/en/latest/admin/sse_updates.html>
5. Hamming AI — transcript retention windows / automated deletion: <https://hamming.ai/resources/pii-redaction-voice-agents-compliance-architecture-guide>
6. DEV — redacting PII in LLM traces without losing debuggability: <https://dev.to/gabrielanhaia/redacting-pii-in-llm-traces-without-losing-debuggability-2jll>
7. DEV — PII in logs (store-then-redact anti-pattern, backups/indices): <https://dev.to/polliog/pii-in-your-logs-is-a-gdpr-time-bomb-heres-how-to-defuse-it-307l>
8. Event-Driven.io — GDPR / forgetting data in event-sourced systems (tombstone/crypto-shred): <https://event-driven.io/en/gdpr_in_event_driven_architecture/>
