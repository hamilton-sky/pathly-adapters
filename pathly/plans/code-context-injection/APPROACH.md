# Code Context Injection (Approach B) — Pathly-native code intelligence

## What this is

This is **Approach B** of the MCP-delivery fork. The other two plans
([gitnexus-integration](../gitnexus-integration/APPROACH.md),
[lsp-integration](../lsp-integration/APPROACH.md)) are **Approach A**: register an MCP server
in each host CLI's config and let the *agent* decide to call it. This plan is the complement:
**Pathly itself queries a code-intelligence backend during runner-mode prompt assembly and
injects the structural facts (blast radius, call chains, references) directly into the agent
prompt** — the agent receives pre-computed context instead of a tool to call.

```
APPROACH A — host MCP install (gitnexus/lsp plans)     "tool-level / agent-driven"
  pathly-setup writes mcp.json ─► host CLI launches gitnexus/serena
        agent (LLM) DECIDES to call the tool when it wants → adaptive, multi-step

APPROACH B — this plan                                  "context-level / Pathly-driven"
  supervisor/runner (Python) ─► Pathly queries the code-intel backend ITSELF
        Pathly injects call-chain / blast-radius INTO the prompt → guaranteed, host-agnostic
```

---

## Why both exist (the fork, stated once)

| | **A — host MCP** | **B — this plan** |
|---|---|---|
| Who runs the query | the agent (LLM), adaptively | Pathly (Python), up front |
| Works in **interactive** (`/pathly explore`) | ✅ (only the host is in the loop) | ❌ Pathly doesn't assemble the prompt here |
| Works in **runner** (Studio Start) | ✅ | ✅ |
| Host-agnostic | ❌ needs each host's MCP support (antigravity unconfirmed) | ✅ any host — Pathly is the single source of truth |
| Deterministic context | ❌ agent *might* not call the tool | ✅ guaranteed in the prompt |
| Adaptive multi-step exploration | ✅ | ❌ one pre-computed shot |
| New code in Pathly | ~none (config only) | a runner-layer provider + injection |

**They compose, they don't compete.** A is required for interactive mode and gives adaptive
exploration; B makes **runner mode** bulletproof and host-independent. The decisive fact: in
interactive mode Pathly never sees the prompt, so only A works; in runner mode Pathly assembles
the prompt (it is the single source of truth — CLAUDE.md), so B can guarantee the structural
context is present and works even on hosts with no MCP support.

This plan is the concrete answer to gitnexus-integration's open question *"Antigravity MCP
support needs verification"* — under Approach B, antigravity needs no MCP support at all.

---

## Goal

In **runner mode**, when a task has code files in scope, deterministically inject a token-budgeted
**"🧭 Code structure (advisory — verify before acting)"** block into the agent prompt containing
the blast-radius / callers / call-chain for those files — sourced by Pathly from a pluggable
code-intelligence backend, with a graceful no-op when none is configured. **Interactive mode is
explicitly out of scope** (that is Approach A's domain — not a gap).

---

## Architecture

Follows the layer rule (`db → runner → supervisor → http_server`; no upward imports) and the
SOLID file rules (one concern per file, ≤400 lines).

```
  supervisor/  ── runner-mode prompt assembly ──► calls runner.code_context.build_block(...)
       │                                                    │
       ▼                                                    ▼
  runner/code_context.py  (NEW)                     CodeContextProvider (pluggable backend)
   • build_block(scope, files, role, budget) -> str   ├─ "none"  → no-op (default)
   • token-budgeted, never raises, "" on failure      ├─ "cli"   → shell out to gitnexus/serena CLI
   • cache by (path, content-hash)                     └─ "mcp"   → Pathly acts as MCP client to
                                                                     gitnexus/serena (reuse A's servers)
```

- **`runner/code_context.py` (NEW)** — owns the one concern: "given files in scope, return an
  advisory structure block." Pure orchestration: pick backend → query → summarize → budget.
  Mirrors `comms_context.retrieve_board_context`'s contract: **never raises; returns `""` on any
  failure** (the "never break the prompt" idiom, F9 in the context-retrieval spec).
- **`CodeContextProvider` interface** with three backends:
  - `none` — default; returns `""`. Pathly ships safe-off.
  - `cli` — shells out to the tool's CLI (e.g. `serena find_referencing_symbols --name X`,
    `gitnexus` impact query). Simplest; no MCP client needed.
  - `mcp` — Pathly becomes an MCP *client* and calls the **same** gitnexus/serena servers
    Approach A installs. Heaviest; reuses A's infrastructure.
- **Injection point** — a new advisory channel appended alongside the existing board-context
  channels, token-budgeted exactly like `comms_context.py`'s `k=3/2/1` caps. It is **advisory**,
  never authoritative: the prompt labels it "verify before acting," same as the 💡 channel.
- **Trigger** — when a runner task carries files in scope (`artifact_path`, `context_refs`, or the
  task's changed-files set), query blast-radius + top callers for those files only (bounded).
- **Caching + staleness** — cache results keyed by `(path, content-hash)`; reuse on unchanged,
  re-query on change. Reuses the `indexed_hash` fingerprint idea from the context-retrieval spec
  so repeated tasks over the same files don't re-pay the query cost.

---

## Configuration — ties into the existing install choice flow

The backend is a single setting: `code_context.backend = off | cli | mcp` (default `off`) plus
`code_context.tool = gitnexus | serena`. This rides the **same install/export selection** the app
already presents (the user chooses which adapters receive skills/agents; this adds "enable
Pathly-native code context, and how"). So the user gets one coherent choice:

```
  Install / Export settings
  ─────────────────────────
  [x] claude    [x] codex   [ ] copilot   [ ] antigravity      ← existing adapter selection
  Code intelligence delivery:
    (•) Host MCP (Approach A)   — installs gitnexus/serena into selected adapters' mcp.json
    ( ) Pathly-native (Approach B) — Pathly injects context  [backend: cli ▾] [tool: gitnexus ▾]
    ( ) Both
    ( ) Off
```

---

## What it touches (backend only)

| What | File | Kind | New/Edit |
|---|---|---|---|
| Code-context provider + backends | `src/pathly_orchestrator/runner/code_context.py` | Python (runner) | **New** |
| Inject the 🧭 channel into runner prompt assembly | supervisor prompt-assembly call site (a few lines) | Python (supervisor) | Edit |
| Backend setting (`code_context.backend`/`tool`) | settings + install choice flow | Python/config | Edit |
| (Optional, deferred) surface the setting in Studio | `studio/` settings panel | TS/React | Edit |

No FSM, no DB schema change (cache can be in-memory or reuse the artifacts index). Studio is
**optional and deferred** — the setting works headless via config first.

---

## Stories (summary — see USER_STORIES.md)

1. `CodeContextProvider` interface + `none` no-op backend (default; never breaks the prompt).
2. A working backend (`cli` first) that returns blast-radius/callers for in-scope files.
3. Inject the token-budgeted 🧭 advisory channel into runner-mode prompt assembly.
4. Content-hash caching + staleness so unchanged files aren't re-queried.
5. Backend config switch wired into the install/export choice flow.
6. Host-agnostic proof: a runner run on a host **without** MCP still gets structural context.

---

## Rollout order

1. Land the interface + `none` backend + injection point (safe no-op end to end).
2. Add the `cli` backend for one tool (gitnexus impact or serena references).
3. Add caching/staleness.
4. Wire the config switch into the install choice flow.
5. (Optional) `mcp` backend reusing Approach A's servers.
6. (Optional) Studio setting surface.

## Sequencing vs Approaches A

- **Independent of A for the `cli` backend** — can ship without gitnexus/lsp host install.
- **The `mcp` backend depends on A's servers existing** (it reuses gitnexus/serena), so build it
  after at least one of the A plans ships.

## Open questions

- **Which signal defines "files in scope"** for a task — `artifact_path` only, `context_refs`, or
  the git changed-set? Start with `artifact_path` + changed-set; widen if under-covered.
- **Summarize vs raw** — inject a summarized impact list (cheaper, lossy) or raw tool output
  (precise, token-heavy)? Default to summarized with a hydrate pointer, mirroring the
  context-retrieval two-tier model.
- **`cli` vs `mcp` as the first backend** — `cli` is simpler and has no client dependency; prefer
  it for v1 unless the chosen tool only exposes MCP.
