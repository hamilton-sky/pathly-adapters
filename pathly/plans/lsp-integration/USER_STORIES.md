# User Stories — lsp-integration

Depends on `gitnexus-integration` having shipped (it builds the MCP-stitching rails and the
agent "code intelligence" prompt section this plan extends). See `APPROACH.md`.

---

## Story 1 — The agent prompt section becomes toolset-neutral and lists LSP

**Who:** Developer maintaining the research agent prompts.
**What:** The `## Tool preference — GitNexus first, Grep/Read fallback` section in `scout.md`,
`quick.md`, and `explorer.md` is renamed to `## Code intelligence — preferred tools,
Grep/Read fallback` and gains LSP (Serena) rows alongside the existing GitNexus rows.
**Why:** One coherent code-intelligence section per agent, not two competing ones; agents get
a single routing rule covering LSP, GitNexus, and Grep.

**Acceptance criteria:**
- `src/pathly_data/core/agents/research/scout.md`, `support/quick.md`, and
  `research/explorer.md` each contain exactly one `## Code intelligence — preferred tools,
  Grep/Read fallback` section and no remaining `## Tool preference — GitNexus first…` heading.
- Each section lists the role's LSP tools and GitNexus tools with native fallbacks, matching
  the per-agent blocks in `APPROACH.md`, and states the "after edits, prefer LSP" rule.
- `pathly-setup claude --apply` succeeds; installed `~/.claude/agents/*.md` reflect the rename.

**Delivered by:** Conversation 1.

---

## Story 2 — Claude adapter tool lists expose the Serena tools per role

**Who:** Developer running a Pathly pipeline on the claude host.
**What:** Each research agent's `_meta` YAML `tools:` list includes the Serena tools it uses.
**Why:** Without the tools in the frontmatter, the claude host will not expose them to the agent.

**Acceptance criteria:**
- `adapters/claude/_meta/scout.yaml` `tools:` =
  `[Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, find_symbol, get_symbols_overview, find_referencing_symbols]`.
- `adapters/claude/_meta/quick.yaml` `tools:` =
  `[Read, Glob, Grep, gitnexus_query, gitnexus_get_context, find_symbol]`.
- `adapters/claude/_meta/explorer.yaml` `tools:` =
  `[Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis, find_symbol, get_symbols_overview, find_referencing_symbols]`.
- `pathly-setup claude --apply` succeeds; installed agent frontmatter reflects the lists.

**Delivered by:** Conversation 1.

---

## Story 3 — Serena MCP config template exists for each adapter

**Who:** Developer running `pathly-setup <host> --apply` after installing Serena/`uv`.
**What:** A `serena.json` MCP template is present in each adapter's `_mcp/` directory.
**Why:** Provides the `mcpServers.serena` block so `pathly-setup`'s `_run_mcp` merges it into
the host config alongside `gitnexus.json`.

**Acceptance criteria:**
- These files exist with identical content matching the template in `APPROACH.md`:
  - `adapters/claude/_mcp/serena.json`
  - `adapters/codex/_mcp/serena.json`
  - `adapters/copilot/_mcp/serena.json`
- Each is valid JSON with `mcpServers.serena.command` = `"uvx"`, the documented `args`, and the
  documented `description`.
- antigravity is skipped (no `_mcp/serena.json`, same as gitnexus).

**Delivered by:** Conversation 2.

---

## Story 4 — pathly-setup merges Serena config alongside GitNexus in one run

**Who:** Developer running `pathly-setup claude --apply`.
**What:** The existing `_run_mcp` step (from gitnexus-integration) picks up `serena.json` via
its `_mcp/*.json` glob and deep-merges `mcpServers.serena` into the host config without
clobbering `gitnexus` or any pre-existing server.
**Why:** Proves the two integrations compose through shared machinery — no new install code.

**Acceptance criteria:**
- After `pathly-setup claude --apply`, `~/.claude/mcp.json` contains BOTH
  `mcpServers.gitnexus` and `mcpServers.serena`.
- Pre-existing unrelated `mcpServers` entries are preserved.
- `pathly-setup claude --apply --dry-run` lists `serena` among servers it would merge.
- If gitnexus-integration has NOT shipped, this story also delivers `_run_mcp` +
  `install.yaml` `mcp:` keys per `APPROACH.md` "Dependency fallback".

**Delivered by:** Conversation 2.

---

## Story 5 — Serena tools available and graceful fallback in a live explore run

**Who:** Developer who has installed `uv` and run a Pathly explore task.
**What:** `/pathly explore` on a specific-symbol question returns findings citing
`find_referencing_symbols` / `find_symbol`; with Serena absent, the same run falls back to
GitNexus or Grep without error.
**Why:** Proves the end-to-end wire and the fallback chain.

**Acceptance criteria:**
- With `uv` installed and `pathly-setup claude --apply` run, a `/pathly explore` on a concrete
  symbol question (e.g. "who calls `stitch_agent`?") produces a TRACE.md referencing a Serena
  tool.
- With Serena removed from `~/.claude/mcp.json`, the same question completes via GitNexus/Grep
  — no crash, no missing-tool error.

**Delivered by:** Conversation 3.
