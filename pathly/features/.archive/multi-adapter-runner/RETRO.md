# Retro — multi-adapter-runner

_Date: 2026-06-02 | Rigor: standard | 3 conversations_

---

## What went well

- **Declarative adapter contract worked perfectly.** `adapters.yaml` + `resolve_command()` eliminated the CLI/UI path disagreement from day one. The anti-drift test caught any generated-file staleness automatically.
- **Threading.Event decision pattern replaced blocking `input()` cleanly.** The non-blocking supervisor loop is the right model for UI-driven pipelines — no thread starvation, clean resume-from-decision semantics.
- **Stage-boundary cap enforcement held up.** Pause, cost cap, and iteration cap are all checked at the loop head, never mid-subprocess. Tests proved the cap stops the run with exactly 1 invocation.
- **Test suite at 325 passing.** Coverage across adapters, endpoints, SSE, caps, session continuity, and stale-mirror recovery gave confident review rounds.

---

## What to improve

- **Missing run_id in `/runner/start` response.** The client needed a run_id to correlate follow-up calls, but the initial response omitted it. Should be a planning-time contract: every async-start API returns a correlation ID.
- **Hardcoded adapter in `runner_terminal_result`** — `parse_result("claude", ...)` was wrong from the start. Multi-adapter code must thread the adapter name through every callsite.
- **`handle_decide()` still using `input()` on the headless path.** The interactive/headless split should be a first-class parameter, not retrofitted. Future features that have both modes should add the flag at design time.
- **`/runner/advance` and `/runner/retry` have no direct tests.** They delegate to tested helpers, but a single smoke-level endpoint test per route would catch future regressions.

---

## Lessons learned

1. **Always return a correlation ID from async-start endpoints.** Any `POST /thing/start` should return `{id}` in the response body — not discoverable later.
2. **Thread adapter name through all parsing callsites at design time.** A hardcoded fallback adapter is always wrong in a multi-adapter system.
3. **The interactive/headless flag is a reusable pattern.** Any CLI wrapper that has both human-driven and programmatic modes should expose `interactive: bool = True` — useful for testing, CI, and non-blocking UI flows.
4. **Threading.Event is the right primitive for UI-driven decision points.** Prefer it over queues for cases where exactly one response unblocks exactly one waiter.
