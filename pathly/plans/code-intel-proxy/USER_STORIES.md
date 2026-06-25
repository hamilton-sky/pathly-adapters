# User Stories — code-intel-proxy (Approach C)

Approach C of the MCP-delivery fork: Pathly is the code-intelligence gateway — agents ask Pathly
over HTTP, Pathly proxies to gitnexus/serena and returns the result. Works in interactive AND
runner mode, for all agent roles. Shares the `runner/code_context` backend with Approach B
(code-context-injection). See `APPROACH.md`.

---

## Story 1 — Reachability prerequisite verified (both modes)

**Who:** Maintainer validating the approach is viable.
**What:** Confirm a runner-spawned agent and an interactive session can each `POST /code/query` to
the FSM HTTP server and receive a response.
**Why:** The entire approach hinges on agents reaching the endpoint; skills already call the FSM
over HTTP, so this should hold — but it must be proven before building on it.

**Acceptance criteria:**
- A documented check shows a runner-mode agent successfully calling `POST /code/query` (even against
  a stub handler) and receiving JSON.
- The same call succeeds from an interactive `/pathly` context.
- If either fails, the failure mode + a mitigation (fall back to Approach B for runner) is recorded
  and the plan pauses.

---

## Story 2 — `POST /code/query` route over the shared backend

**Who:** Any agent (via the shim) needing callers / blast-radius / symbols.
**What:** A `POST /code/query` route in a new `code/` blueprint domain validates a
`{op, target, args}` request, calls the shared `runner/code_context` backend, and returns the result.
**Why:** This is the gateway — the single proxy entry point.

**Acceptance criteria:**
- `http_server/blueprints/code/query.py` exists; the route follows the comms blueprint idiom (lazy
  imports, `request.get_json()` validation, structured error codes).
- Valid `op` values (`impact|callers|symbol|pattern`) dispatch to the backend; invalid input returns
  `400` with a structured error.
- With backend `none`/disabled, the route returns `{"ok": true, "result": null, "backend": "none"}`
  (HTTP 200) — never a 500 — so the agent degrades to Grep.
- The route imports only from `runner`/`db` (layer rule); no upward imports.

---

## Story 3 — `pathly-fsm-call code-query` agent shim

**Who:** Any agent in interactive or runner mode.
**What:** A `code-query` subcommand on the existing `pathly-fsm-call` CLI lets an agent call the
endpoint with simple args, mirroring `pathly-fsm-call record-activity`.
**Why:** Gives every agent role a uniform way to ask Pathly, no host MCP support required.

**Acceptance criteria:**
- `pathly-fsm-call code-query --op impact --target <path>` posts to `/code/query` and prints the
  JSON result.
- It works against the running FSM server in both modes.
- Missing/unreachable server fails gracefully with a clear message, non-zero exit, no traceback dump.

---

## Story 4 — Gateway central control: cache + comms-board logging + routing

**Who:** Operator running many tasks; agents needing fresh, deduped context.
**What:** The gateway caches results by `(target, content-hash)`, logs each query to the comms board
as a `discovery`, and routes per `op` to the configured backend (gitnexus vs serena vs grep).
**Why:** This is the leverage only the gateway provides — one place for freshness, sharing, routing.

**Acceptance criteria:**
- A repeat query over an unchanged target is a cache hit (no backend re-invoke); editing the target
  invalidates it (shared with B's cache).
- Each query posts a `discovery` to the comms board for the active scope (so lookups become shared
  board context), best-effort and never blocking the response.
- `op` → backend routing is configurable and falls back to Grep when the chosen backend is absent.

---

## Story 5 — Agents are told the gateway exists (all roles)

**Who:** Every agent, not just scout/quick/explorer.
**What:** The `## Code intelligence — preferred tools, Grep/Read fallback` section gains an "or ask
Pathly via `code-query`" row, and it is added to the relevant agent prompts beyond the research roles
(e.g. builder, reviewer) so any agent can use the gateway.
**Why:** Code awareness helps all agents; the gateway makes that uniform.

**Acceptance criteria:**
- The shared code-intelligence prompt section documents the `code-query` gateway option with its
  request shape and the Grep fallback.
- At least builder and reviewer (in addition to scout/quick/explorer) carry the section.
- `pathly-setup claude --apply` propagates the updated prompts without error.

---

## Story 7 — User can enable/disable the capability (settings + permission)

**Who:** User who wants to decide whether agents have code intelligence at all.
**What:** A setting group (`code_intel.enabled`, `code_intel.surfaces`, `code_intel.roles`) gates
the capability. Disabling it (a) removes the `## Code intelligence` prompt fragment on the next
`pathly-setup --repair` so agents are never told the ability exists, and (b) makes
`POST /code/query` refuse at runtime.
**Why:** The user — not the plan — owns whether agents get this ability, with a real runtime switch.

**Acceptance criteria:**
- The `## Code intelligence` section is delivered as a **fragment** under
  `core/skills/fragments/` (composed via `compose.py`), not a hard-coded edit — so it can be
  included/excluded by the setting.
- With the capability disabled and `pathly-setup --repair` run, materialized agents/skills contain
  **no** `## Code intelligence` section.
- With the capability disabled at runtime, `POST /code/query` returns
  `{"ok": true, "result": null, "reason": "disabled"}` (or `403`) without invoking any backend.
- The `code_intel.roles` allowlist is enforced by `/code/query`: a call from a role not on the list
  is refused; a call from a permitted role succeeds.
- Default is disabled (no behavior change for existing installs).

---

## Story 6 — (Optional) `pathly-code` MCP shim republishing typed tools

**Who:** User on a host that prefers real MCP tool affordances.
**What:** A thin Pathly-owned stdio MCP server (`pathly-code`) republishes typed tools
(`pathly_code_impact`, `pathly_code_callers`, …) with schemas and forwards to `POST /code/query`,
installed via Approach A's `_run_mcp` rails.
**Why:** Gives the LLM first-class tool schemas while keeping Pathly the single gateway.

**Acceptance criteria:**
- A `pathly-code` MCP server forwards each typed tool call to `/code/query` and returns the result.
- An `_mcp/pathly-code.json` template exists for the relevant adapters and merges via `_run_mcp`.
- With the shim absent, the CLI-shim path (Story 3) still fully works — the shim is additive.
