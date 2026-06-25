# Code Intel Proxy (Approach C) — Pathly as the code-intelligence gateway

## What this is

**Approach C** of the MCP-delivery fork. Instead of each host CLI connecting to gitnexus/serena
(Approach A) or Pathly pre-injecting context into runner prompts (Approach B), **the agent asks
Pathly, and Pathly proxies the query to the real code-intelligence backend**, then returns the
result. The agent gets adaptive, on-demand code intelligence — in **both** interactive and runner
mode, for **every** agent role — through a single Pathly-owned gateway.

```
  agent (ANY role, interactive OR runner)
        │  asks Pathly:  code-query { op: "impact", target: "src/install_cli/stitch.py" }
        ▼
  Pathly FSM HTTP server (127.0.0.1:8765)  ── Pathly is the PROXY/GATEWAY ──┐
        │   new POST /code/query route                                       │
        │   → shared runner/code_context backend (none | cli | mcp-client)   │
        │   → gitnexus / serena                                              │
        │   ◄──────────────── result ───────────────────────────────────────┘
        ▼
  Pathly can cache · log to comms board · route backend · budget · return JSON
```

### Why HTTP, not "MCP tools for sub-agents"

The grounding fact (verified in this repo): **`pathly-fsm` is an HTTP server on port 8765**, and
agents *already* call it — skills hit `/next_action`, `/record_activity`, etc. via the
`pathly-fsm-call` CLI (`pyproject.toml` → `pathly-fsm-call`, README port 8765). So Approach C is
**one more endpoint on a server every agent already reaches**, in both modes. This is the literal
realization of your "agent calls HTTP to Pathly, Pathly calls the tool" — no new transport, no
dependency on the host exposing MCP tools to sub-agents.

---

## Relationship to A, B, and the shared backend

This is the third surface of the MCP-delivery fork. The decisive comparison:

| | A — host MCP | B — Pathly injects | **C — Pathly proxy (this)** |
|---|---|---|---|
| Interactive mode | ✅ | ❌ | **✅** |
| Runner mode | ✅ | ✅ | **✅** |
| Adaptive (agent calls on demand, multi-step) | ✅ | ❌ | **✅** |
| Host-agnostic | ❌ N host configs | ✅ | **✅ (HTTP server agents already use)** |
| Single integration point | ❌ | ✅ | **✅** |
| Central control (cache / governance / comms-board / routing) | ❌ | ✅ | **✅ (best — a live router)** |
| Reaches **all** agent roles (not just research) | only those given the tools | only those whose prompt is injected | **✅ any agent that can call the endpoint** |
| New code in Pathly | ~none (config) | backend + injection | backend + HTTP route + agent shim |

**C and B share one backend.** Both call the same `runner/code_context` provider (the
`none | cli | mcp-client` core + content-hash cache + backend routing). B *pre-injects* its output
into the prompt; C *serves* it on demand via HTTP. **Building either one builds the shared core** —
see `../code-context-injection/APPROACH.md` ("Shared backend"). The three surfaces:

```
            ┌──────────────────────────────────────────────┐
            │   SHARED: runner/code_context provider        │
            │   none | cli | mcp-client → gitnexus/serena   │
            │   + content-hash cache + backend routing      │
            └──────────────────────────────────────────────┘
              ▲                  ▲                    ▲
   surface A  │       surface B  │         surface C  │
   host MCP   │       inject     │         proxy endpoint
   (no Pathly │       (runner,   │         (interactive + runner;
    dep)      │        determin- │          adaptive; ALL agents;
              │        istic)    │          this plan)
```

---

## Goal

Expose Pathly as a code-intelligence gateway: a `POST /code/query` endpoint on the FSM HTTP server
that proxies a `{op, target, args}` request to the shared backend and returns structured results,
plus an agent-facing shim (`pathly-fsm-call code-query …`) so any agent — interactive or runner —
can ask for callers / blast-radius / symbols on demand. Pathly owns caching, backend routing,
comms-board logging, and token budgeting at the gateway.

---

## Architecture

Follows the layer rule (`db → runner → supervisor → http_server`) and the blueprint domain map.

- **New blueprint domain `code/`** (no existing domain fits — the map says create a new domain
  file rather than overload an unrelated one). Route: `POST /code/query`.
  - Handler follows the comms blueprint idiom: lazy imports inside the function,
    `request.get_json()` validation, structured `jsonify({"error":...}), <code>`.
  - Calls `runner.code_context` (http_server → runner is allowed). Returns JSON.
- **Shared backend** = `runner/code_context.py` from Approach B (`none | cli | mcp-client`
  backends, content-hash cache, backend routing). C adds **no new backend** — it reuses B's.
- **Request shape** — two options:
  - **Typed (recommended):** `{ "op": "impact|callers|symbol|pattern", "target": "...", "args": {} }`
    — clearest for the agent and easiest to validate.
  - **Generic passthrough:** `{ "tool": "gitnexus_impact_analysis", "request": {...} }` — simplest,
    mirrors upstream schemas, but weaker affordance. Start typed; passthrough is a fallback.
- **Agent-facing surfaces (how the agent reaches the route):**
  1. **CLI shim (primary)** — `pathly-fsm-call code-query …`, mirroring the existing
     `pathly-fsm-call record-activity` (`src/install_cli/orchestrate.py:169`). Any agent invokes it
     via its normal tool use; works interactive + runner, all roles, no host MCP needed.
  2. **Optional MCP shim (deferred)** — a thin Pathly-owned stdio MCP server (`pathly-code`) that
     republishes typed tools with schemas and forwards to `POST /code/query`, installed via
     Approach A's `_run_mcp` rails for hosts that prefer real MCP tool affordances.
- **Central control at the gateway** — cache by `(target, content-hash)` (shared with B); log each
  query to the comms board as a `discovery` (so code lookups become shared board context); route to
  gitnexus vs serena vs grep per `op`; enforce a result-size budget.
- **Safety** — the endpoint never 500s on a backend miss: a missing/disabled backend returns
  `{ "ok": true, "result": null, "backend": "none" }` so the agent degrades to Grep, never crashes.

---

## Capability control (settings & permission)

The user decides whether agents get code intelligence *at all*, and how. **One setting group gates
all three surfaces** — but the gate differs by surface because Pathly is in the call loop for B/C
and **not** for A.

**Setting model** (written by the install/export choice flow; stored in central config, e.g.
`~/.pathly`):
- `code_intel.enabled` — master on/off
- `code_intel.surfaces` — `{ host_mcp (A), inject (B), proxy (C) }`, each on/off
- `code_intel.roles` — optional allowlist of agent roles permitted to use B/C (e.g. only
  `explorer, reviewer, builder`)
- `code_intel.backend` / `code_intel.tool` — `cli|mcp` / `gitnexus|serena` (from Approach B)

**Two gates, exactly the two mechanisms you described:**

1. **Prompt fragment — "tell the agent it has the ability."** The `## Code intelligence` section is
   delivered as a **conditional fragment** (Pathly already composes skills from
   `core/skills/fragments/` via `compose.py` / `fsm_ops.py`). When a surface is disabled,
   `pathly-setup --repair` re-materializes agents/skills **without** the fragment — the agent is
   never told the ability exists. *Install-time* gate (applies on next apply/repair).

2. **Runtime permission — "actually allow the call."**
   - **B:** `backend=off` → `build_block` returns `""` → nothing injected. Instant.
   - **C:** `POST /code/query` checks `enabled` + `surfaces.proxy` + the **caller's role** against
     `roles`; if not permitted it returns `{ "ok": true, "result": null, "reason": "disabled" }`
     (or `403`). Instant — **no reinstall**. This is the literal "condition that does not give
     permission to call the MCP through Pathly."

**The asymmetry (why C is the strongest control point):**
- **A is install-time-only.** Once gitnexus/serena sits in the host's `mcp.json` and the agent's
  tool list, the **host** offers the tool to the model — Pathly is not in that path, so it cannot
  refuse at runtime or per role. Disabling A = drop the server from `mcp.json` + remove the fragment,
  then reinstall.
- **B and C pass through Pathly**, so they are runtime-gated. **Only C supports per-role permission**,
  because every call crosses its checkpoint.

Net: for a real-time on/off the user flips, rely on **C's endpoint check**; the **fragment** is the
"don't even mention it" cleanup applied on the next `--repair`.

---

## Critical prerequisite (Conversation 1)

The whole approach hinges on **agents being able to reach the FSM HTTP endpoint in both modes.**
This is *already true for skills* (they call `/next_action` / `/record_activity` over HTTP today),
so confidence is high — but Conv 1 must explicitly verify a spawned runner agent AND an interactive
session can both successfully `POST /code/query` and get a result, before anything else is built.

---

## What it touches (backend; one optional CLI shim)

| What | File | Kind | New/Edit |
|---|---|---|---|
| `POST /code/query` route | `http_server/blueprints/code/query.py` (new domain) | Python (http_server) | **New** |
| Shared backend (reused from B) | `runner/code_context.py` | Python (runner) | (shared with B) |
| Agent CLI shim `code-query` | `fsm.http_client` / `pathly-fsm-call` entry | Python | Edit |
| Comms-board logging of queries | existing `/comms` post path (lazy call) | Python | Edit |
| `## Code intelligence` section as a conditional **fragment** | `core/skills/fragments/` + `compose.py` wiring | data + Python | New/Edit |
| Capability setting + endpoint permission check | install choice flow + `code/query` handler | Python/config | Edit |
| (Optional, deferred) `pathly-code` MCP shim + install template | `adapters/*/_mcp/pathly-code.json` | data | New |

No FSM state-machine change, no DB schema change (cache reuses B's content-hash store; logging
reuses comms). No frontend.

---

## Stories (summary — see USER_STORIES.md)

1. Prereq verification — a runner agent and an interactive session can both reach `POST /code/query`.
2. `POST /code/query` route (new `code/` domain) calling the shared backend; safe-null on no backend.
3. `pathly-fsm-call code-query` CLI shim so any agent can call it in either mode.
4. Gateway central control — content-hash cache + comms-board logging + per-op backend routing.
5. Agent prompts/skills tell agents the gateway exists (the `## Code intelligence` section gains a
   "or ask Pathly via code-query" row) — extends to **all** roles, not just research agents.
6. (Optional) `pathly-code` MCP shim republishing typed tools via Approach A's rails.

---

## Rollout order

1. Verify reachability (prereq) — runner + interactive both `POST /code/query`.
2. Land `POST /code/query` over the shared backend (safe-null when backend off).
3. Add the `code-query` CLI shim.
4. Add gateway cache + comms-board logging + routing.
5. Advertise it in agent prompts/skills (all roles).
6. (Optional) ship the `pathly-code` MCP shim for hosts that want real MCP tools.

## Sequencing vs A and B

- **Depends on the shared backend** (`runner/code_context` from Approach B). Build B's backend
  core first (or build it here and B consumes it) — they are one effort.
- The `mcp-client` backend reuses Approach A's servers, so the `cli` backend is the right v1 for C.
- Independent of A's host-install otherwise — C needs no host mcp.json.

## Open questions

- **Typed ops vs generic passthrough** as the request shape — default typed; revisit if upstream
  tools change often.
- **Auth/scope on the endpoint** — `/code/query` is loopback-only like the rest of the FSM server;
  confirm no broader exposure is introduced.
- **Result granularity** — return summarized impact + a hydrate pointer (cheap) vs raw tool output
  (precise, token-heavy); mirror the context-retrieval two-tier model. Default summarized.
