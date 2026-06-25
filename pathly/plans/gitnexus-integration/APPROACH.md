# GitNexus Integration — Approach

## What is GitNexus

GitNexus (https://github.com/abhigyanpatwari/GitNexus) is a codebase knowledge graph that
parses any repo with Tree-sitter, builds a dependency/call-chain graph, and exposes it via
an MCP server (16 tools). Supported languages: TypeScript, JavaScript, Python, Java, Kotlin,
C#, Go, Rust, PHP, Ruby, Swift, C, C++, Dart.

---

## Goal

Give Pathly's read-only research agents (scout, quick, explorer) structural codebase awareness
without the token cost of repeated grep/read cycles. GitNexus is preferred when available;
agents fall back to native tools (Grep, Read) when it is not.

> **MCP-delivery fork.** This plan is **Approach A** — register an MCP server in the host CLI
> and let the agent call it (tool-level, agent-driven; works in interactive + runner; relies on
> host MCP support). The complementary **Approach B** — Pathly queries the code-intel backend
> itself and injects the result into runner-mode prompts (host-agnostic, deterministic) — lives
> in [`../code-context-injection/APPROACH.md`](../code-context-injection/APPROACH.md). They
> compose; A is required for interactive mode.

---

## What it touches

This plan is config-as-feature: agent prompts + `_meta` tool-lists + `_mcp/*.json` templates,
plus one Python function (`_run_mcp`) in `src/install_cli/orchestrate.py`. **No frontend (Studio),
no FSM/orchestrator, no DB changes.** A full touch-surface table and ASCII diagrams (install-time
stitching + run-time tool routing, covering this plan and lsp-integration together) live in
[`../lsp-integration/APPROACH.md`](../lsp-integration/APPROACH.md) → "What it touches + how it works".

---

## Tool-by-query-type mapping

Each agent uses a subset of GitNexus tools matched to the kind of query it performs:

| Query type | GitNexus tool | Native fallback |
|---|---|---|
| Find symbol / pattern | `gitnexus_query` | Grep |
| Understand a function (callers, callees, deps) | `gitnexus_get_context` | Read + Grep |
| Trace execution path end-to-end | `gitnexus_get_call_chain` | Read chains |
| Blast radius of a change | `gitnexus_impact_analysis` | Grep for references |

---

## Per-agent changes

### scout
**Core prompt addition (`scout.md`):**
Add a "Code intelligence" section after the Scope rules block:
```
## Code intelligence — preferred tools, Grep/Read fallback
When GitNexus MCP tools are available, prefer them over native tools:
- Find a symbol or pattern         → gitnexus_query          (fallback: Grep)
- Understand callers / callees     → gitnexus_get_context     (fallback: Read + Grep)
- Trace an execution path          → gitnexus_get_call_chain  (fallback: Read chains)
If GitNexus tools are not available, proceed with Grep and Read as normal.
```

**Claude adapter `_meta/scout.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain]
```
(no impact_analysis — scout does not assess change blast radius)

---

### quick
**Core prompt addition (`quick.md`):**
Add after the "2 tool call" constraint:
```
## Code intelligence — preferred tools, Grep/Read fallback
Prefer GitNexus tools when available — they count as 1 tool call each:
- Symbol lookup    → gitnexus_query or gitnexus_get_context  (fallback: Grep or Read)
If GitNexus tools are not available, proceed with Grep and Read as normal.
```

**Claude adapter `_meta/quick.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context]
```
(only the two fast-lookup tools — quick never traces paths or assesses blast radius)

---

### explorer
**Core prompt addition (`explorer.md`):**
Add a "Code intelligence" section in the Information gathering block:
```
## Code intelligence — preferred tools, Grep/Read fallback
When GitNexus MCP tools are available, prefer them over Read/Grep for:
- Symbol and pattern search         → gitnexus_query
- Understanding a function          → gitnexus_get_context
- Tracing execution paths           → gitnexus_get_call_chain
- Assessing blast radius of change  → gitnexus_impact_analysis  (only explorer uses this)
Scouts spawned by explorer inherit this preference automatically via their own prompts.
If GitNexus tools are not available, proceed with Glob, Grep, Read as normal.
```

**Claude adapter `_meta/explorer.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis]
```
(all 4 tools — explorer is the only role that does blast-radius analysis)

---

## MCP server setup per adapter

GitNexus runs as: `gitnexus mcp` (stdio MCP server).

The MCP config template lives in each adapter's install layer and is stitched by
`pathly-setup <host> --apply`. It is **optional** — if the user has not run
`gitnexus analyze` on their repo, agents fall back to native tools gracefully.

| Adapter | Config file to create | Location after install |
|---|---|---|
| `claude` | `adapters/claude/_mcp/gitnexus.json` | merged into `~/.claude/mcp.json` |
| `codex` | `adapters/codex/_mcp/gitnexus.json` | merged into `~/.agents/mcp.json` |
| `copilot` | `adapters/copilot/_mcp/gitnexus.json` | merged into `.vscode/mcp.json` |
| `cursor` | `adapters/cursor/_mcp/gitnexus.json` | merged into `.cursor/mcp.json` |
| `antigravity` | TBD — verify agy MCP support first | TBD |

Template content (same for all adapters):
```json
{
  "mcpServers": {
    "gitnexus": {
      "command": "gitnexus",
      "args": ["mcp"],
      "description": "Codebase knowledge graph — query symbols, call chains, and impact analysis"
    }
  }
}
```

---

## Rollout order

1. Verify `gitnexus mcp` stdio contract matches the 4 tool names used above
   (`gitnexus_query`, `gitnexus_get_context`, `gitnexus_get_call_chain`, `gitnexus_impact_analysis`)
2. Update core agent prompts (`scout.md`, `quick.md`, `explorer.md`)
3. Update Claude adapter `_meta` YAMLs (tools lists)
4. Create `_mcp/gitnexus.json` template for each adapter
5. Update `pathly-setup` to stitch `_mcp/*.json` into host MCP config
6. Test with `gitnexus analyze` on this repo, then run `/pathly explore` on a real question

---

## Open question

- Antigravity (agy CLI) MCP support needs verification before adding its template.
- Cursor adapter does not yet exist in this repo — add alongside the new adapters initiative.
