# Board Lifecycle — Findings, Applied Fixes, and Open Proposals

_Author: Claude (Opus 5) · Date: 2026-08-24 · Status: **2 fixes applied, 5 proposals awaiting your call**_

Evidence base: the `local-usage-meter` feature board in
`~/Documents/project/token-tracker/pathly/`, read live from the running orchestrator on
`127.0.0.1:8765` — 71 messages, 4 goals, 14 tasks, 10 billed agent runs, `STATE.json: DONE`.

---

## TL;DR

Pathly's context layer is better than most agent frameworks ship. Governance is injected
unconditionally, auto-derived context honestly labels itself `UNVERIFIED`, the catalog keeps
current summaries, and there's a coverage metric for curated refs. Those are the hard parts.

Every defect found sits in the same place: **nothing closes.** Decisions never supersede, agent
resolutions never write back to task state, human gates never actually gate, and the token
telemetry couldn't measure itself. One shape, four times — the board is append-only truth where
nothing ever wins.

Two of those I fixed. The rest change agent behaviour, so they're yours to decide.

---

## Part 1 — Applied fixes

### Fix 1 — Prompt-cache tokens were collapsed into `tokens_in`

**Severity: high.** This is the bug that makes Pathly's cost numbers wrong, and it is the exact
bug the `local-usage-meter` brief calls "the top accuracy bug" — sitting inside the tool whose
feature board is chartered to fix it.

**What was happening.** `runner/output.py::_claude_tokens` deliberately folds cache reads and
cache creation into a single `tokens_in` lump ("matching the lump `tokens_in` convention"). That
lump is the correct *total* but the wrong *basis for pricing*: cache reads bill at 0.1× and cache
writes at 1.25×/2× depending on TTL. The chain had no producer for the split at all:

```
_claude_tokens         folds cache into tokens_in
  → BILLING_UPDATE     carries no cache fields
    → invocation_projection   never writes the columns
      → trends.py      SUMs cache_read_tokens / cache_write_tokens → always 0
```

`agent_invocations.cache_read_tokens` and `.cache_write_tokens` have existed since the schema was
added, and `db/queries/trends.py` has summed them the whole time. Nothing ever populated them.
Live confirmation from the running server:

```json
GET /telemetry/trends?feature=local-usage-meter
{"count":10, "input_tokens":7647470,
 "cache_read_tokens":0, "cache_write_tokens":0,
 "total_tokens":7731382, "cost_usd_reported":8.29166115}
```

7.65M "input" tokens and not one cache token, on a 10-run agent workload where the overwhelming
majority of input is cache reads.

**Why it mattered.** `/telemetry/pricing` exposed only `input` and `output` rates — a two-bucket
world. Priced that way, this run computes to **$24.20** against the **$8.29** the CLI actually
reported: a 2.9× overstatement. It was latent rather than charged, because it only fires on rows
where the CLI reported no cost (`cost_source="estimated"`) — but those rows exist, and they were
3× wrong. Any Pathly budget, trend line, or cost alert built on estimated rows inherits it.

**What I changed** (6 files, all additive — `tokens_in` keeps its cache-inclusive meaning so no
existing reader shifts):

| File | Change |
|---|---|
| `runner/output.py` | New `extract_cache_tokens()`; `parse_result()` returns the split alongside the lump |
| `runner/events.py` | `_patch_last_agent_done()` takes and emits `cache_read_tokens` / `cache_write_tokens` |
| `supervisor/terminal_billing.py` | Threads both through from the parsed result |
| `db/queries/invocation_projection.py` | `_fold_billing` folds them; the `UPDATE` persists them; the split is passed to pricing |
| `db/pricing.py` | `CACHE_READ_MULTIPLIER = 0.1`, `CACHE_WRITE_MULTIPLIER = 2.0` on the input rate; carved out of the lump before pricing; both surfaced on `/telemetry/pricing` |

**Verification:**

```
lump (old behaviour)      : $24.20
cache-tiered (new, 2.0x)  : $5.04     (95% read / 2% write assumption)
actually reported by CLI  : $8.29
zero split == old result  : True      ← backwards compatible
clamp when split > lump   : holds     ← a malformed pair can't refund the bill
unknown model             : (0.0, 'unpriced')   ← unchanged
estimate_cost_for 3-arg   : works     ← legacy callers unaffected
```

The remaining gap to $8.29 is the read/write ratio, which is assumed here rather than known —
once real splits land in the columns the estimate resolves against actual values.

**The write multiplier is 2.0×, and that was measured, not assumed.** This shipped as 1.25×
(Anthropic's 5-minute ephemeral tier) on the reasoning that 5m is Claude Code's default and the
result envelope doesn't break cache creation out by TTL. **Both halves of that are wrong.**
Measured against a real 3,683-line Claude Code session log on 2026-08-24:

| Measurement | Result |
|---|---:|
| turns carrying `usage.cache_creation` | **1,772 / 1,772 (100%)** |
| `ephemeral_1h_input_tokens` (bills 2×) | **3,713,390 (100%)** |
| `ephemeral_5m_input_tokens` (bills 1.25×) | **0 (0%)** |

Pricing agent runs at 1.25× understates the cache-write line by **37.5%**. The constant is now
2.0×. `CACHE_WRITE_5M_MULTIPLIER = 1.25` is recorded but unused — splitting the two tiers through
the pipeline needs a third token column plus a migration, and with the 5m share measured at 0%
the accuracy gain today is nil. That's a deliberate deferral, noted in the source.

**Historical rows are still wrong.** This fix only corrects runs from here on; existing
`agent_invocations` rows have `cache_read_tokens = cache_write_tokens = 0` and will keep reading
as pure uncached input. If the Studio trend chart matters, those rows need backfilling from
`EVENTS.jsonl` or flagging as pre-fix.

### Fix 2 — Governance decisions rendered in an order that hid supersession

**Severity: high** — this is what corrupted the `local-usage-meter` board.

`get_pending_decisions` returns `ts ASC` and `_format_age` renders day granularity. Eight
decisions made across one afternoon all rendered as an indistinguishable `13d ago`, oldest first.
The block injected into every builder contained both of these as equal, live governance:

- *"ARCH_QUESTION 2 remains a hard human gate before P1 BUILD."* — architect, **15:05**
- *"Adopt Option B … Phase 1 is fully unblocked. Task b7d9a7af is COMPLETE."* — evaluator, **17:20**

with no way to tell which won. Same block also carried *"TUI uses Ink (React-for-CLI)"* as active
governance while the architecture's ADR-007 explicitly rejects Ink and the task's own acceptance
text says "no Ink/React runtime".

**What I changed** — `runner/comms_context.py`, rendering only:

- Decisions sort **newest-first** with a `LATEST ·` marker on the top entry.
- Minute-precision stamps alongside the age (`2026-08-10 17:20 · 13d ago`) — same-day decisions
  are the ones that actually conflict, and "13d ago" cannot order them.
- An explicit precedence line: *"If two decisions conflict, the one listed FIRST wins."*
- When decisions are newer than an open escalation, a note fires: *"An agent decision does NOT
  close a human gate — only a human acknowledgement does. Treat the gate as OPEN."*

**This is a bandage on Proposal A below.** Ordering is the cheap half of supersession; until
`superseded_by` is actually set, recency is the only signal a reader has.

---

## Part 2 — Open proposals

Each of these changes agent or FSM behaviour, so I stopped at diagnosis.

### Proposal A — Nothing ever calls `POST /comms/supersede` · **highest value**

`superseded_by` is set on **0 of 71** messages on this board.

The mechanism is fully built and working: the column exists (`migrations_incremental.py:96`),
`supersede_message()` is implemented with proper `not_found` / `already_superseded` handling,
`POST /comms/supersede` is routed, and both `get_pending_decisions` and `get_active_escalations`
already filter on it. `/comms/consolidate` even uses it for near-duplicate notes.

No agent-facing path ever calls it. Decisions are posted via `/comms/post` and simply accumulate.

**Suggested fix:** let `/comms/post` accept an optional `supersedes: [id, ...]` and call
`supersede_message` in the same transaction; then teach the decision-posting skills to populate
it. A cheaper 80% version: when an agent posts a `decision` whose text starts with `RESOLVED —`
or `UNBLOCKED —`, auto-supersede the most semantically similar prior decision in the same scope
(the embeddings are already there — 160 rows on this board).

### Proposal B — Agent resolutions never write back to task state

`BOARD_EVAL.md` ends with *"Mark tasks `726aecdd`, `4a0a6706`, `b7d9a7af` as COMPLETE."* Live
board, 14 days later: all three still `task_status=pending`, `attempts=0`, `claimed_by=null`. So
are the other eleven.

The evaluator was the most expensive role on this board — **$3.05 of the $8.29**, four separate
runs — and its entire output was prose instructing a state change nobody executed. It resolved
three blockers into a markdown file while the board's system of record still says they're open.

**Suggested fix:** give the evaluator a real tool (`/comms/tasks/status`) and make "mark complete"
a call, not a sentence. If an agent can't be trusted to mutate task state directly, have it emit a
structured `proposed_transitions` block that the orchestrator applies or surfaces for one-click
approval — but the resolution must land *somewhere* other than prose.

### Proposal C — Human gates don't gate

Four board messages are still `status=pending` with `acknowledged_by=[]` and `read_by=[]`:

| Message | From | Posted |
|---|---|---|
| escalation — "Human checkpoint required — HUMAN_QUESTIONS.md" | system | 09:21 |
| question — daemon self-spawns without explicit consent | architect | 09:21 |
| warning — "Option B is not recommended", needs explicit human answer | evaluator | 15:00 |
| constraint — "DEDUP IS MANDATORY before aggregation" | architect | 09:21 |

The FSM ran `PO_DISCUSSING → ARCHITECTING → RESEARCHING → DESIGNING → PLANNING → DONE` past all
four. The checkpoint mechanism fires correctly and then blocks nothing.

Worse, the same role that raised a gate can dissolve it. At 15:00 the evaluator warned that
Option B "is not recommended" and required an explicit human answer before BUILD; at 17:20 the
evaluator adopted Option B. Total human input on this board across the entire run: **one
sentence** — *"Use `Defer to build`. Keep it simple."*

**Suggested fix:** an unacknowledged `escalation` should block the specific transition it names,
not the whole FSM. And an agent should be structurally unable to resolve an escalation raised for
`to_agent: human` — that resolution needs a human `acknowledge_message()` call.

### Proposal D — `STATE.json: DONE` on a board with zero delivered work

The feature reports `DONE` with 14/14 tasks pending and an empty `src/`. $8.29, 65 minutes, six
agents, 7.65M tokens, ~1,650 lines of markdown, zero lines of code.

A terminal state that says "done" when nothing shipped is an honesty problem in the FSM, not just
in the telemetry. **Suggested fix:** `DONE` should require the goals' tasks to be terminal.
Otherwise this state is `PLANNED`, and calling it that costs nothing and misleads nobody.

### Proposal E — Two telemetry stores that don't know about each other

```
GET /comms?feature=local-usage-meter        → 71 messages
GET /telemetry/trends?feature=...           → the billing row
GET /api/features                           → []
GET /api/features/local-usage-meter/metrics → {"event_count":0,"invocation_count":0,"span_count":0}
GET /api/features/local-usage-meter/events      → {"events":[],"total":0}
GET /api/features/local-usage-meter/artifacts   → []
```

The `/api/features/*` surface is blind to a board that the `/comms` and `/telemetry` surfaces see
fully. Whichever one the Studio UI reads determines whether this feature appears to exist.

**Related, lower priority:** the agents' self-reported `AGENT_DONE.total_tokens` disagree with
`BILLING_UPDATE` by up to ~175× (evaluator's final run self-reports `12000`; billing says
`2096717`). Since `BILLING_UPDATE` supersedes it for display this is mostly cosmetic — but
anything reading `AGENT_DONE` directly is off by two orders of magnitude.

### Proposal F — 0% context-ref coverage, measured and ignored

`GET /comms/goals/refs-coverage` reports `coverage_pct: 0.0` for all four goals — 14/14 tasks with
no curated `context_refs`. The endpoint exists specifically to measure this and nothing acts on it.

The injection layer compensates well (governance + catalog + honestly-labelled semantic matches),
so this is **not urgent** — but note what the semantic fallback surfaced for the scaffold task: its
top hit, flagged `match: strong`, was the *stale* architect summary describing "ccusage **embedded**
behind a compatibility port" — the strategy research had already killed. Curated refs would have
pinned the current one.

**Suggested fix:** have the planner populate `context_refs` at decompose time, or fail a goal that
decomposes to <50% coverage.

---

## Part 3 — Suggested order

1. **Proposal A** (supersession write path) — root cause of the board's self-contradiction; my
   Fix 2 is only masking it.
2. **Proposal B** (decision write-back) — makes the most expensive agent role's output real.
3. **Proposal C** (gates that gate) — the safety property you probably thought you had.
4. **Proposal D** (`DONE` means done) — one predicate, big honesty win.
5. **Proposal E / F** — cleanup.

Then re-run `local-usage-meter` end to end. With A–D in place it becomes a genuine test of whether
Pathly can ship code, rather than a test of whether it can produce documents.

---

## Appendix — Files touched

**Modified (fixes applied):**

```
src/pathly_orchestrator/runner/output.py
src/pathly_orchestrator/runner/events.py
src/pathly_orchestrator/runner/comms_context.py
src/pathly_orchestrator/supervisor/terminal_billing.py
src/pathly_orchestrator/db/queries/invocation_projection.py
src/pathly_orchestrator/db/pricing.py
```

All six compile; imports verified; legacy call signatures preserved via defaults.
**The running server holds the old code — restart to load these:**

```bash
curl -s -X POST http://127.0.0.1:8765/shutdown
```

**Not touched:** no database rows were modified, no board state mutated, no FSM transition run.
Everything in Part 2 is diagnosis only.

**Caveat worth stating:** `~/Documents/project` has no git commits and `pathly-adapters/` is
untracked, so there was no version-control safety net for these edits. Backups of all six
originals were written to this session's scratchpad, but they are session-scoped and will not
survive indefinitely — `git init && git add -A && git commit` before the next agent run would be
worth more than any fix in this document.
