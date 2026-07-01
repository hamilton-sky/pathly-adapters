# Code-Intel Backend Decision — replacing gitnexus

**Status:** recommendation (ready to implement)
**Context:** gitnexus is broken on this Windows/Node22 box (`worker_threads` native crash). It is the data source for the `cli` backend (B/C) **and** the host-MCP server (A). All three surfaces need a Windows-safe, multi-language replacement.
**Grounding:** `src/pathly_orchestrator/runner/code_context.py`, `http_server/blueprints/code/query.py`, the 3-surface APPROACH docs, the on-disk `_mcp/*.json` templates and `_run_mcp` stitcher.

---

## TL;DR

> **Split by job, not one tool for everything.** Use a **two-tool pairing** that maps cleanly onto the index-vs-LSP tradeoff:
>
> - **`codebase-memory-mcp` (pre-indexed graph) = the DEFAULT** for B/C and the primary new server for A. It is the only candidate that is a **single static binary with pre-built Windows binaries, zero deps, multi-language (158 langs via vendored tree-sitter), AND ships both an MCP server and a JSON-returning CLI.** That CLI is the drop-in gitnexus replacement for the existing `cli` backend; the MCP server is the drop-in gitnexus replacement for A's `mcp.json`. It answers the graph-wide questions gitnexus owned (blast-radius, call-chain, references) with no Node-native-worker fragility.
> - **Serena (LSP-over-MCP) = the freshness companion**, A-only, already wired. Keep it for *post-edit, single-symbol* correctness where a pre-built index can be stale. **Do not put Serena behind the `cli` backend** — it is MCP-only (no structured-JSON CLI), and its uvx-from-git cold start violates the headless constraint.
>
> **One change in `code_context.py`:** generalize `CliProvider` from a gitnexus-shaped command to a **config-driven command template** (tool name + per-op argv + a small JSON-parse step), then set `code_context.tool = codebase-memory-mcp`. No `mcp-client` backend needed yet — the chosen graph tool already speaks CLI-JSON, which is strictly simpler than embedding an MCP client in Python.
>
> **Agent prompt tool-lists change minimally:** drop `mcp__gitnexus__*`, keep `mcp__serena__*`, and add the new graph server's `mcp__<graph>__*` tools for A. B/C need no tool-list change (the agent calls `pathly-fsm-call code-query`, not an MCP tool).

```
                      ┌──────────── DEFAULT ────────────┐   ┌─── COMPANION ───┐
  Surface A (MCP)  ►  │  codebase-memory-mcp  (graph)   │ + │  serena (LSP)   │
  Surface B/C      ►  │  codebase-memory-mcp CLI → JSON │   │     (A-only)    │
                      │  via generalized CliProvider     │   └─────────────────┘
                      └──────────────────────────────────┘
       gitnexus ✗ removed everywhere (Node22 worker_threads crash)
```

---

## 1. Primary recommendation

### The pick: `codebase-memory-mcp` as the spine, Serena as the freshness edge

| | Serves surface | Pathly backend | Why it wins on the 5 constraints |
|---|---|---|---|
| **`codebase-memory-mcp`** | **A** (its MCP server) + **B/C** (its CLI) | `cli` (generalized) | **Windows:** pre-built Windows static binary, zero deps — sidesteps the exact `worker_threads` crash class. **Multi-lang:** 158 langs (vendored tree-sitter). **Headless:** pre-built SQLite graph → queries are fast (Linux kernel indexed in ~3 min once; per-query is instant), no per-query cold start. **Pathly-queryable:** the `cli` subcommand returns JSON → drops into the existing `CliProvider` shape. **Local:** SQLite on disk, no egress. |
| **Serena** | **A** only | none (MCP, agent-driven) | Already wired (21 tools verified on this box). Owns the one thing a pre-built graph can't: *always-fresh, compiler-grade* single-symbol references/definitions right after an edit. uvx cold start is acceptable for an interactive A session; unacceptable behind B/C — so it stays A-only. |

### Why a split, not one tool

Each family is strong at the opposite thing, and the constraints push the *default* toward the graph:

```
        PRE-INDEXED GRAPH (codebase-memory-mcp)   LSP (Serena/agent-lsp)
        ───────────────────────────────────────   ──────────────────────
fast    whole-repo blast-radius in ONE query  ✓    one symbol per call
fresh   can be stale until re-index           ✗    always exact, post-edit ✓
headless instant query, no cold start         ✓    uvx-from-git cold start ✗
windows  static binary, prebuilt              ✓✓   uvx/pip, ok but slower
multi   158 langs                             ✓    40+ langs                ✓
CLI-JSON yes → drops into `cli` backend       ✓    MCP only, no JSON CLI    ✗
```

The decisive facts: (1) **B/C run inside short-lived headless agents** — the headless constraint forbids a multi-second uvx cold start per query, which rules Serena out of the `cli` backend. (2) **Only the graph tool exposes a JSON CLI**, so only it drops into the `cli` backend without writing an MCP client. (3) **gitnexus's whole reason to exist was graph-wide blast-radius/call-chain** — `codebase-memory-mcp` replaces that capability one-for-one and on the same surface, with a static Windows binary. Serena stays as the A-surface freshness companion because that is exactly the gap a pre-built index leaves (and it is already installed).

### Could ONE tool serve all three?

Considered and rejected for now:
- **codebase-memory-mcp alone (graph-only):** loses post-edit freshness. Acceptable as a *floor* — if you want to ship the smallest change, ship just this and keep Serena around for interactive A. But the freshness gap is real after edits, and Serena is already wired, so dropping it is needless capability loss.
- **agent-lsp alone (LSP-only, warm daemon):** very attractive on paper — explicit Windows support (winget/scoop/pip/npm), a **warm-daemon** model (~10s first index, instant after, auto-exit 30 min) that *does* satisfy the headless constraint, references/definitions/**call-hierarchy/blast-radius**, 65 MCP tools. Its one disqualifier for the *default*: **no confirmed structured-JSON CLI** for the `cli` backend (it is MCP-first). So it can serve A immediately but would require the `mcp-client` backend for B/C. **It is the strongest fallback** (see §4) and the right pick if codebase-memory-mcp's Windows binary or CLI-JSON fails validation, or if you decide the warm-daemon "always fresh + graph in one tool" story is worth building the `mcp-client` backend for.

---

## 2. The index-vs-LSP tradeoff — how Pathly routes

The two families are a **freshness/scope tradeoff**, and Pathly already has the seam to route them per surface and per op.

```
  QUESTION TYPE                         ROUTE TO              WHY
  ────────────────────────────────────  ────────────────────  ─────────────────────────
  "blast radius of changing this file"  graph (impact)        whole-graph in ONE query
  "full call chain end-to-end"          graph (chain)         graph traversal, one shot
  "every reference to symbol X"         graph (callers) ...   fast, good enough pre-edit
       ...but JUST edited X?            LSP (find_referencing) always-fresh, exact
  "where is X defined"                  LSP (find_symbol)     compiler-exact
  "outline this file"                   LSP (get_symbols_*)   structural, cheap
  "fuzzy / name unknown"                Grep                  meaning-based discovery
  nothing installed                     Grep / Read           graceful fallback
```

**Two routing rules (these are the same rules the lsp-integration APPROACH already states — now made the system contract):**

1. **Freshness tiebreaker — LSP wins post-edit.** A pre-built graph is stale until re-indexed. After a file has changed, single-symbol reference/definition questions should trust LSP over the graph. *This is the precise weakness the graph leaves and LSP cancels.*
2. **Narrowest-correct-tool-first.** Precise single-symbol → LSP. Cross-cutting / graph-wide → graph. Neither present → Grep.

**Where each surface routes:**
- **A (host-MCP):** the *agent* routes, guided by the `## Code intelligence` prompt section. Both servers are in `mcp.json`; the prompt tells it "graph for blast-radius/chain, LSP for exact single-symbol especially after edits." This is already drafted in `lsp-integration/APPROACH.md` — it just swaps the gitnexus rows for the new graph tool's rows.
- **B (inject) / C (proxy):** **Pathly routes**, deterministically, in `build_block()` / the `_gate` op-tiering. These surfaces default to the **graph** because (a) it satisfies the headless no-cold-start constraint and (b) B/C's bread-and-butter is exactly the pre-computed blast-radius/callers block. **Post-edit freshness on B/C is intentionally deferred** — B/C are advisory ("verify before acting") and the agent can fall through to A's Serena or Grep for exact post-edit checks. A future `code_context.tool = serena` path via an `mcp-client` backend is the upgrade lane if B/C ever need always-fresh, but it is not needed for the gitnexus replacement.

> **Net routing policy:** *graph is the default everywhere; LSP is the agent-driven freshness override on A.* B/C are graph-only by design and lean on A/Grep for the post-edit exact case.

---

## 3. Concrete migration from gitnexus

Four mechanical changes. Nothing in the FSM, DB, or Studio.

### 3a. `code_context.py` — generalize `CliProvider` from gitnexus-shaped to config-driven

The current provider hard-codes gitnexus's command shape: `["impact", path]` and `["context", path]`, raw-text stdout, `"not indexed"` sentinel. Generalize it so the **tool, its per-op subcommands, and a JSON-extract step** come from config, not code.

**What changes (same file, ≤400-line rule respected — this is a refactor, not growth):**

- Replace the two hard-coded gitnexus calls in `_file_section` with a **per-op command table** resolved from the tool config, e.g. a small dict the provider builds from `code_context.tool`:
  ```
  TOOL_COMMANDS = {
    "codebase-memory-mcp": {
      "impact":  ["cli", "query_graph",  '{"op":"impact","target":"{path}"}'],
      "callers": ["cli", "search_graph", '{"op":"references","target":"{path}"}'],
      # exact subcommands/op names per the tool's `cli` contract — VALIDATE (see §4)
    },
    "gitnexus": {   # kept only as a legacy reference; gitnexus removed from default
      "impact":  ["impact", "{path}"],
      "callers": ["context", "{path}"],
    },
  }
  ```
- Add a **JSON-parse + summarize step** in `_run` (or a new `_run_json`): the graph CLI returns JSON, so parse it and render a compact summary into the section instead of pasting raw text. Keep the `""`-on-any-failure contract (a parse error degrades to `""`, same as today). This is the one genuinely new behavior — gitnexus returned prose, the graph tool returns JSON.
- Keep **everything else identical**: the content-hash cache (`_CLI_CACHE`), the concurrent bounded subprocess wait (`_await_or_empty` / `ThreadPoolExecutor` / `shutdown(wait=False)`), `_CLI_MAX_FILES`, `_CLI_TIMEOUT_S`, the never-raise contract. The static-binary tool is *faster* than node, so the existing 8s timeout is comfortable. (Consider dropping `_CLI_TIMEOUT_S` to ~5s once the static binary is confirmed; not required.)

The provider's docstring/comments that name gitnexus ("Node startup ~5s", "gitnexus impact/context") should be updated to describe the generalized contract.

### 3b. `code_context.tool` config evolves

`_resolve_tool()` currently allows `{"gitnexus", "serena"}` and defaults to `gitnexus`. Change to:

```
_resolve_tool():  allow {"codebase-memory-mcp", "gitnexus", "serena"}
                  default → "codebase-memory-mcp"   (was "gitnexus")
```

- **`serena` stays an accepted value but is a no-op for the `cli` backend** (Serena has no JSON CLI). It only becomes live if/when an `mcp-client` backend is added. Document this so the value isn't mistaken for a working `cli` path. (Cleanest: have `CliProvider` treat `serena` as "no command table → return `''`", preserving safe-off.)
- The install/export choice flow's `[tool: gitnexus ▾]` dropdown (drafted in `code-context-injection/APPROACH.md`) changes its default option to the graph tool and lists `codebase-memory-mcp | serena | gitnexus(legacy)`.
- `code_context.backend` is unchanged: `off | cli`. **No `mcp` backend is added now** — the chosen tool's CLI makes it unnecessary. The Protocol's `name` comment (`none | cli | mcp`) can keep `mcp` as a reserved/future value.

### 3c. Surface A — swap the MCP server template; keep Serena

The `_run_mcp` stitcher already deep-merges any `adapters/*/_mcp/*.json`, so this is pure data:

- **Add** `adapters/{claude,codex,copilot,antigravity}/_mcp/codebase-memory-mcp.json` (the graph server's `mcpServers` block — `command` = the static binary, `args` = its `mcp` subcommand). Because `_run_mcp` globs `_mcp/*.json`, it lands alongside `serena.json` automatically — both servers in one `pathly-setup` run, same as gitnexus+serena did.
- **Remove** `adapters/*/_mcp/gitnexus.json` (4 files). gitnexus is dead on this box; leaving it would try to launch the crashing binary.
- **Keep** `adapters/*/_mcp/serena.json` (3 files) unchanged.

### 3d. Agent prompt tool-lists — drop gitnexus, add the graph tool, keep serena

The tool-lists already use the `mcp__<server>__<tool>` form (confirmed in `_meta/explorer.yaml`: `mcp__gitnexus__query, …, mcp__serena__find_symbol, …`). So this is a find/replace across the three research agents + their `_meta`:

| File set | Change |
|---|---|
| `core/agents/research/{scout,explorer}.md`, `support/quick.md` | In the `## Code intelligence` section, replace the gitnexus rows with `mcp__<graph>__*` rows (impact/references/call-chain). Keep the Serena rows. Keep the "after edits, prefer LSP" line — it is now the routing contract. |
| `adapters/claude/_meta/{scout,quick,explorer}.yaml` `tools:` | Remove `mcp__gitnexus__*`; add the graph server's tool names; keep `mcp__serena__*`. |
| All four adapters | Re-sync via `pathly-setup claude --apply --repair` + `python -m build` (core→adapter sync rule). |

**B/C tool-lists do NOT change.** B injects a block (no tool). C is reached via `pathly-fsm-call code-query` (a CLI shim, not an MCP tool). The `code/query` role-tiering (`_TIER_OPS`/`_ROLE_TIER`) is tool-agnostic and stays as-is — its op names (`impact|callers|chain|symbol|context|pattern`) map onto the graph CLI's ops in the §3a command table.

### Migration diff at a glance

```
  REMOVE  adapters/*/_mcp/gitnexus.json            (4 files)
  ADD     adapters/*/_mcp/codebase-memory-mcp.json (4 files)
  KEEP    adapters/*/_mcp/serena.json              (3 files, unchanged)

  EDIT    runner/code_context.py
            • CliProvider: gitnexus-shaped cmd → config-driven command table
            • add JSON-parse/summarize for graph CLI output
            • _resolve_tool default gitnexus → codebase-memory-mcp
            • keep cache / bounded-wait / never-raise verbatim
  EDIT    core/agents/{scout,explorer,quick}.md  — graph rows swap, Serena kept
  EDIT    adapters/claude/_meta/{scout,quick,explorer}.yaml — tools: swap
  UNCHANGED  http_server/blueprints/code/query.py — tool-agnostic gateway
  UNCHANGED  FSM, DB, Studio
```

---

## 4. Ranked shortlist + what to validate next

### Shortlist (B/C `cli` backend + A graph server)

| Rank | Tool | Role | Verdict |
|---|---|---|---|
| **1 (DEFAULT)** | **codebase-memory-mcp** | graph spine for A + B/C | Single static binary, **pre-built Windows binaries**, zero deps, 158 langs, **MCP server + JSON CLI**, SQLite, fast. Hits all 5 constraints; the only candidate that serves A *and* drops into the existing `cli` backend. |
| **2 (FALLBACK)** | **agent-lsp** | warm-daemon LSP for A + (via new `mcp-client`) B/C | Explicit Windows support, **warm daemon** (satisfies headless), call-hierarchy + blast-radius, 30 langs. Fallback only because it has **no confirmed JSON CLI** → B/C would need the `mcp-client` backend. Pick this if #1 fails validation or you want one always-fresh tool for everything. |
| 3 | Serena | LSP companion, **A-only** | Keep regardless — post-edit single-symbol freshness. Not a `cli`-backend candidate (no JSON CLI; uvx cold start). |
| 4 | CodeGraph | graph (alt) | #1 by stars, SQLite, MCP — but **Windows support unconfirmed**. Only if codebase-memory-mcp's Windows binary disappoints AND agent-lsp is rejected. |
| 5 | SCIP indexers | graph (alt, precise) | Language-agnostic SCIP index + `scip` CLI; precise protobuf. Heavier integration (per-language indexers, no single MCP). Strategic backstop, not v1. |
| ✗ | gitnexus | — | **Removed.** Node22 `worker_threads` crash. |
| ✗ | CodeGraphContext | graph (alt) | MCP+CLI, but no Windows-specific evidence; redundant with #1. |

### Validate next (in this order — gate the migration on the first two)

1. **codebase-memory-mcp Windows binary indexes THIS repo.** Install the pre-built Windows binary; run its index/build on `pathly-adapters` (Python `src/` + TypeScript `studio/`). Confirm it completes without a native crash and produces a SQLite graph. *(This is the gitnexus killer — prove the replacement doesn't share the failure mode.)*
2. **Its `cli` subcommand returns parseable JSON for the three ops we need.** Run `codebase-memory-mcp cli search_graph '{…}'` (and the impact/call-chain equivalents) and confirm: (a) stdout is JSON, (b) it contains references/callers/blast-radius for a known symbol in this repo, (c) the op names map onto `impact|callers|chain`. *(This is what makes the `cli`-backend generalization a 1-file change instead of an `mcp-client` build.)*
3. **Its MCP server launches and lists tools on Windows** (`mcp__<server>__*`), for surface A — so the `_mcp/codebase-memory-mcp.json` template + tool-list swap actually expose tools to the agent.
4. **Cold-vs-warm query latency** under the headless budget: confirm a single `code-query` round-trip stays well under `_CLI_TIMEOUT_S` (8s) on the pre-built index. (Expected easily, given "Linux kernel in 3 min" indexing and instant queries — but measure on this box.)
5. **If #1 or #2 fail → pivot to agent-lsp:** validate its Windows install (winget/scoop/pip), warm-daemon first-index (~10s) + instant-after, and decide whether to (a) use it A-only + keep graph-less B/C on Grep, or (b) build the `mcp-client` backend so B/C speak MCP to its daemon.

### Decisive default

**Ship codebase-memory-mcp as the graph spine (A + B/C via a generalized `cli` backend), keep Serena as the A-only freshness companion, delete gitnexus.** It is the single pick that clears Windows + multi-language + headless-cold-start simultaneously and reuses the `cli` backend you already built. Hold agent-lsp as the funded fallback the moment validation step 1 or 2 fails.
