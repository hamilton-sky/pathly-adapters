# LSP Integration (Serena MCP) — Approach

## What is LSP / Serena

**LSP (Language Server Protocol)** is a standard where a per-language *language server*
(pyright, tsserver, rust-analyzer, gopls, …) performs compiler-grade semantic analysis of
the live code and answers structured queries: go-to-definition, find-all-references,
call hierarchy, symbol outline, safe rename. Unlike a pre-built index, **LSP answers are
always fresh and exact** — they compute against the current files, so they never go stale
after an edit.

**Serena** (https://github.com/oraios/serena) is an MCP server that wraps LSP and exposes
these operations as agent tools. Its read-only / navigation tools:

| Serena tool | What it returns |
|---|---|
| `get_symbols_overview` | Symbol outline of a file/dir (top-level classes, functions) |
| `find_symbol` | Locate a symbol by name path (e.g. `UserService/authenticate`), optionally with its body |
| `find_referencing_symbols` | Every real call site of a symbol from the language server's reference index ("the tool grep pretends to be") |
| `search_for_pattern` | Regex search with surrounding semantic context |

(Serena also has editing tools — `replace_symbol_body`, `insert_after_symbol` — which
Pathly's **read-only research agents do not use**. Only the four navigation tools above
are wired here.)

---

## Goal

Give Pathly's read-only research agents (scout, quick, explorer) **precise, always-fresh**
structural code awareness via LSP. LSP is the right tool when correctness on a *specific
symbol* matters (exact references, exact callers) and especially **after code has been
edited**, where a pre-built graph index can be stale. Agents fall back to native tools
(Grep, Read) when Serena is not available.

---

## Relationship to `gitnexus-integration` (read this first)

This plan is the **second** code-intelligence integration and is deliberately small because
it **reuses the rails the gitnexus-integration plan builds**:

1. **MCP-stitching machinery** — `gitnexus-integration` Story 5 adds `_run_mcp` to
   `src/install_cli/orchestrate.py` and an `mcp:` key to each adapter's `install.yaml`,
   deep-merging `_mcp/*.json` templates into the host MCP config. This plan only **adds one
   more template file** (`_mcp/serena.json`) — no new install machinery.
2. **The agent prompt "code intelligence" section** — `gitnexus-integration` already ships a
   neutral `## Code intelligence — preferred tools, Grep/Read fallback` section in `scout.md`,
   `quick.md`, `explorer.md` (GitNexus rows only). This plan **adds the LSP rows** to that
   existing section, so both integrations live in one coherent section — no rename needed.

**Sequencing:** ship `gitnexus-integration` first (it builds the rails). This plan layers on
top. If gitnexus has NOT shipped, this plan must create the `_run_mcp` machinery itself —
see "Dependency fallback" at the end.

---

## How GitNexus and LSP are used together (the routing rule)

They are complementary, not redundant. Strong at opposite things:

| The agent's question | Use | Why |
|---|---|---|
| "Where is `X` defined?" / "exact references to `X`?" / "who calls `X`?" (one symbol) | **LSP** (`find_symbol`, `find_referencing_symbols`) | Always-fresh, compiler-exact; correct even right after an edit |
| "Full call chain end-to-end" / "**blast radius** of changing this module" / "map the dependency graph" | **GitNexus** (`gitnexus_get_call_chain`, `gitnexus_impact_analysis`) | Whole-graph answer in one query; LSP can't do graph-wide in one call |
| "Find code *about* X" / symbol name unknown / fuzzy | semantic search / `search_for_pattern` / Grep | Meaning-based discovery |
| Nothing installed | **Grep / Read** | Graceful fallback |

Two rules that make "both" coherent:

- **Freshness tiebreaker:** after code has been edited, trust **LSP over GitNexus** — GitNexus
  is a pre-built index and may be stale until re-`analyze`d. This is the exact weakness LSP
  cancels out.
- **Narrowest-correct-tool-first:** precise single-symbol question → LSP; cross-cutting
  graph question → GitNexus; neither present → Grep.

---

## Tool-by-query-type mapping

| Query type | LSP (Serena) tool | GitNexus equivalent | Native fallback |
|---|---|---|---|
| Find a symbol / its definition | `find_symbol` | `gitnexus_query` | Grep |
| Outline a file's symbols | `get_symbols_overview` | — | Read |
| Who references / calls a symbol (exact, fresh) | `find_referencing_symbols` | `gitnexus_get_context` | Grep for references |
| Pattern search with semantic context | `search_for_pattern` | `gitnexus_query` | Grep |

(No LSP equivalent of `gitnexus_impact_analysis` in one call — blast-radius across the graph
stays GitNexus's job; LSP confirms precise callers symbol-by-symbol via
`find_referencing_symbols`.)

---

## Per-agent changes

The agent prompt section is the neutral `## Code intelligence — preferred tools,
Grep/Read fallback` heading already shipped by `gitnexus-integration`. This plan adds the LSP
rows to it. Each role lists the subset it uses.

### scout
**Core prompt (`scout.md`), in the renamed section:**
```
## Code intelligence — preferred tools, Grep/Read fallback

Prefer semantic code tools over native Grep/Read when available.
LSP (Serena) — precise, always fresh; best for a specific symbol:
- Find a symbol / its definition   → find_symbol               (fallback: Grep)
- Outline a file's symbols         → get_symbols_overview      (fallback: Read)
- Who calls / references a symbol  → find_referencing_symbols  (fallback: Grep)
GitNexus — graph-wide; best for whole-repo call chains:
- Find a symbol or pattern         → gitnexus_query            (fallback: Grep)
- Understand callers / callees     → gitnexus_get_context      (fallback: Read + Grep)
- Trace an execution path          → gitnexus_get_call_chain   (fallback: Read chains)
After code has been edited, prefer LSP over GitNexus (LSP is always fresh).
If neither toolset is available, proceed with Grep and Read as normal.
```

**Claude adapter `_meta/scout.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, find_symbol, get_symbols_overview, find_referencing_symbols]
```

---

### quick
**Core prompt (`quick.md`), in the renamed section:**
```
## Code intelligence — preferred tools, Grep/Read fallback

Prefer semantic tools when available — each counts as 1 tool call:
- Symbol lookup    → find_symbol or gitnexus_query   (fallback: Grep or Read)
If neither is available, proceed with Grep and Read as normal.
```

**Claude adapter `_meta/quick.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context, find_symbol]
```
(quick's 2-call budget: one fast LSP/GitNexus symbol lookup; it never traces chains or
assesses blast radius)

---

### explorer
**Core prompt (`explorer.md`), in the renamed section:**
```
## Code intelligence — preferred tools, Grep/Read fallback

Prefer semantic code tools over Read/Grep.
LSP (Serena) — precise, always fresh; confirm specific callers/definitions:
- Find a symbol / definition       → find_symbol
- Outline a file's symbols         → get_symbols_overview
- Exact callers of a symbol        → find_referencing_symbols
GitNexus — graph-wide; the only source of whole-repo blast radius:
- Symbol and pattern search        → gitnexus_query
- Understand a function            → gitnexus_get_context
- Trace execution paths            → gitnexus_get_call_chain
- Blast radius of a change         → gitnexus_impact_analysis  (explorer only)
Use gitnexus_impact_analysis for the wide sweep, then find_referencing_symbols to
confirm the precise, current callers on the live code. After edits, trust LSP.
Scouts spawned by explorer inherit this preference via their own prompts.
If neither toolset is available, proceed with Glob, Grep, Read as normal.
```

**Claude adapter `_meta/explorer.yaml` tools list:**
```yaml
tools: [Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis, find_symbol, get_symbols_overview, find_referencing_symbols]
```

---

## MCP server setup per adapter

Serena runs as a stdio MCP server. Recommended launch (no global install needed beyond `uv`):

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--context", "ide-assistant", "--project-from-cwd"],
      "description": "LSP-powered semantic code tools — symbols, references, call sites (always fresh)"
    }
  }
}
```

The template lives in each adapter's `_mcp/` directory and is stitched by the SAME
`_run_mcp` step that gitnexus-integration adds to `pathly-setup`. It is **optional** — if
Serena / `uv` is not installed, agents fall back to GitNexus or native tools gracefully.

| Adapter | Config file to create | Stitched into |
|---|---|---|
| `claude` | `adapters/claude/_mcp/serena.json` | `~/.claude/mcp.json` |
| `codex` | `adapters/codex/_mcp/serena.json` | `~/.agents/mcp.json` |
| `copilot` | `adapters/copilot/_mcp/serena.json` | `.vscode/mcp.json` (workspace-local) |
| `antigravity` | skipped | (agy MCP support unconfirmed — same skip as gitnexus) |

Because `_run_mcp` globs `_mcp/*.json` and merges every server it finds, `serena.json`
sitting alongside `gitnexus.json` means **both** servers land in the host config in one
`pathly-setup` run. No orchestrate.py change needed if gitnexus-integration shipped.

---

## Rollout order

1. **Verify Serena's contract** — confirm the four tool names (`find_symbol`,
   `get_symbols_overview`, `find_referencing_symbols`, `search_for_pattern`) and the
   `start-mcp-server` launch args against the current Serena release.
2. **Add the LSP rows** to the existing `## Code intelligence — preferred tools, Grep/Read
   fallback` section in `scout.md`, `quick.md`, `explorer.md` (per-agent blocks above). The
   section already exists (shipped by gitnexus-integration) — no rename needed.
3. **Update Claude adapter `_meta` YAMLs** — add the Serena tool names to the `tools:` lists.
4. **Create `_mcp/serena.json`** for each adapter (claude, codex, copilot).
5. **Propagate** — `pathly-setup claude --apply` (reuses gitnexus's `_run_mcp`).
6. **Smoke test** — install `uv`, run `/pathly explore` on a concrete symbol question, confirm
   the trace cites `find_referencing_symbols` evidence; then with Serena absent, confirm
   graceful fallback to GitNexus/Grep.

---

## Open questions / risks

- **`uv` / language-server availability.** Serena needs `uv` (`uvx`) on PATH and a language
  server per language. Document this as a prerequisite; the fallback chain (GitNexus → Grep)
  must hold when it's missing.
- **Project root arg.** `--project-from-cwd` assumes the agent runs in the repo root. Verify
  this holds for runner-mode spawns; a `${workspaceFolder}`-style substitution may be needed
  for copilot/workspace-local installs.
- **Startup latency.** LSP servers index on first start (seconds to tens of seconds on large
  repos). Acceptable for interactive sessions; verify it doesn't stall short headless runs —
  if it does, prefer GitNexus for one-shot headless agents and reserve Serena for interactive.

## Dependency fallback (if gitnexus-integration has NOT shipped)

If this plan is built first, it must also do gitnexus-integration's Story 4/5 work:
add `_run_mcp` to `src/install_cli/orchestrate.py` and the `mcp:` key to each adapter's
`install.yaml` (see `../gitnexus-integration/CONVERSATION_PROMPTS.md` Conversation 2 for the
exact implementation). Prefer not to — ship gitnexus first.
