# Let the chief read daycap's machine-wide daily spend

Type: task (round-two draft; was round-one ticket 18)
Status: deferred to round two (2a)
Blocked by: round one built; round-one ticket 19's answer
Test first: yes

> **Moved out of round one on 2026-10-14.** Round one is the chief's server core and the bar in
> map.md; this is a reporting surface, like `GET /chief/overview`, and ticket 13's acceptance does
> not cover it. Round two (2a) plans it from this draft. Fix these before it becomes a ticket:
>
> - **No `billing/` package.** `src/pathly_orchestrator/billing/` sits outside the layer rule
>   (`db -> runner -> supervisor -> http_server`) and the import-linter contract in
>   `pyproject.toml`. The reader has no internal imports, so it fits in `runner/` (for example
>   `runner/daycap_snapshot.py`).
> - **No new route domain.** No blueprint domain is called `billing`. Spend reporting is
>   telemetry, so the route goes in `blueprints/ops/` next to `telemetry.py` (for example
>   `GET /telemetry/daycap`).
> - **One door for the chief.** Drop step 1's `Bash(daycap today *)` and `Bash(daycap doctor *)`
>   allows. `pathly spend` over the route gives the chief the same number through its token and
>   the gate, and adds no second program to the chief's allow list.
> - **Pin the format.** The reader depends on daycap's private cache (`~/.daycap/state`, schema
>   1, integer cents). Accept only schema 1 and answer `available: false` for anything else, so a
>   daycap upgrade degrades to "unknown" instead of a wrong number.
> - Whatever ticket 19 finds goes into the style text's wording about what daycap can stop.
>
> The ticket text below is the original draft, kept as written; its "ticket NN" references are
> round-one ticket numbers.

daycap (the local budget guardrail: `~/Documents/project/daycap`) owns the
machine-wide daily budget across every AI coding tool the user runs. It
caches a `UsageSnapshot` (schema 1, per-tool spend in integer cents,
freshness/health flags, timezone-aware day window) under `~/.daycap/state`
(fallback `~/.localusagemeter/state`, key `"today"`; see daycap
`src/app/meter.ts::buildSnapshot`, `SNAPSHOT_KEY`). Ticket 15 caps what a
chief *session* may start; daycap knows what the *machine* has spent. The
chief should be able to read and report that number.

1. Extend the chief's claude settings (ticket 06) with read-only daycap
   commands: `Bash(daycap today *)` and `Bash(daycap doctor *)`. Never
   `daycap install *`, `daycap config --edit`, or any `--write` form: those
   move the budget fences and stay human-only, like `PUT /db/settings`
   (ticket 15). The codex chief keeps no daycap access (no hook, no shell
   trust boundary to reason about yet).
2. Add a server-side reader, `src/pathly_orchestrator/billing/daycap.py`,
   that loads the cached snapshot from the state dir (no subprocess, no
   collector access — read the file daycap already wrote) and returns
   `{today_usd, budget_usd, pct_of_budget, per_tool: {tool: usd},
   fresh: bool, source_id}` or `{"available": false, "reason"}` when the
dir, file, or schema is missing/unreadable. Fail closed on *reporting*,
   never on *enforcement*: a missing snapshot is reported as unknown, it
   never blocks a call (enforcement is ticket 19's question).
3. `GET /billing/daycap` serves the reader's output. The chief gate
   (ticket 08) maps it to the `read` action, so every tier may call it.
   The `pathly` CLI (ticket 17) gains `pathly spend` printing the same.
4. The built-in style texts (ticket 17) gain two lines: the chief may
   answer "how much have I spent today" from daycap (machine-wide, not
   just Pathly), and it proactively tells the user when daycap reports at
   or past the 80% threshold.

The two spend lenses stay separate on purpose: Pathly's `cost_usd`
(AGENT_DONE, per run/stage/session) drives Pathly's ceilings (ticket 15);
daycap's snapshot drives the machine-wide daily view. Never sum them —
they are two measurements of overlapping tokens.

Living docs: `daycap` in the "Chief gate" paragraph of
`src/pathly_orchestrator/CLAUDE.md` (read-only, all tiers).

## Not in this ticket

- Enforcement (blocking spawns when daycap is over budget): ticket 19
  determines what daycap's guard actually covers first.
- Writing daycap's config or budget from Pathly: human-only, permanently.
- A Studio spend widget: round two, built on `GET /billing/daycap`.

## Done when

- `python -m pytest tests/http_api/test_chief_daycap.py -q -p no:cacheprovider`
  passes and covers, with a fake `~/.daycap/state` (via `HOME` override):
  `GET /billing/daycap` returns the snapshot's totals in USD with per-tool
  breakdown; a missing dir returns `available: false`; a schema-mismatched
  file returns `available: false` (never raises); a status-tier chief token
  gets 200; the chief's claude settings allow `daycap today` and still deny
  `daycap install --write`; each built-in style text names the spend
  question and the 80% warning.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_daycap.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- ticket 06 (chief claude settings), ticket 08 (gate `read` action),
  ticket 15 (session ceilings; `PUT /db/settings` refused for chiefs),
  ticket 17 (`pathly` CLI, built-in style texts)
- daycap `src/app/meter.ts` (`buildSnapshot`, `SNAPSHOT_KEY = "today"`),
  `src/domain/types.ts` (`UsageSnapshot`), `src/bin/guard.js` (state dir
  resolution, `~/.daycap` then `~/.localusagemeter` fallback)

## Answer
