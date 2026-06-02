# User Stories — gitnexus-integration

## Story 1 — Scout prefers GitNexus tools when available

**Who:** Developer running a Pathly pipeline that spawns a scout agent.
**What:** The scout agent uses `gitnexus_query`, `gitnexus_get_context`, and `gitnexus_get_call_chain` when those MCP tools are available in the session.
**Why:** Avoids repeated Grep/Read cycles for symbol lookups and call-chain traces, reducing token cost and increasing structural accuracy.

**Acceptance criteria:**
- `src/pathly_data/core/agents/research/scout.md` contains a `## Tool preference — GitNexus first, Grep/Read fallback` section positioned after `## Output format` and before `## Hard constraints — READ ONLY`.
- That section lists the three tools (`gitnexus_query`, `gitnexus_get_context`, `gitnexus_get_call_chain`) and their native fallbacks (`Grep`, `Read + Grep`, `Read chains`) in the exact format specified in `APPROACH.md`.
- `src/pathly_data/adapters/claude/_meta/scout.yaml` `tools:` list is `[Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain]`.
- Running `pathly-setup claude --apply` succeeds without error after the changes.
- The installed agent file at `~/.claude/agents/scout.md` contains the `## Tool preference` section and the updated `tools:` frontmatter.

**Delivered by:** Conversation 1, Phase 1.

---

## Story 2 — Quick prefers GitNexus tools when available

**Who:** Developer running a Pathly skill that spawns a quick lookup agent.
**What:** The quick agent uses `gitnexus_query` or `gitnexus_get_context` for symbol lookups before falling back to Grep or Read.
**Why:** GitNexus lookups count as one tool call each, fitting within the quick agent's 2-call budget while returning richer structural context.

**Acceptance criteria:**
- `src/pathly_data/core/agents/support/quick.md` contains a `## Tool preference — GitNexus first, Grep/Read fallback` section positioned after `## Role lens` and before `## Called by skill orchestrators`.
- That section explicitly notes that each GitNexus call counts as 1 tool call and lists `gitnexus_query` and `gitnexus_get_context` with their fallbacks.
- `src/pathly_data/adapters/claude/_meta/quick.yaml` `tools:` list is `[Read, Glob, Grep, gitnexus_query, gitnexus_get_context]`.
- Running `pathly-setup claude --apply` succeeds without error.
- The installed `~/.claude/agents/quick.md` contains the updated section and frontmatter.

**Delivered by:** Conversation 1, Phase 2.

---

## Story 3 — Explorer prefers all four GitNexus tools when available

**Who:** Developer running `/pathly explore` on a structural question.
**What:** The explorer agent uses all four GitNexus tools (`gitnexus_query`, `gitnexus_get_context`, `gitnexus_get_call_chain`, `gitnexus_impact_analysis`) in the appropriate phase, preferring them over native file reads.
**Why:** Explorer is the only role that performs blast-radius analysis; `gitnexus_impact_analysis` gives it graph-based change impact that Grep alone cannot provide.

**Acceptance criteria:**
- `src/pathly_data/core/agents/research/explorer.md` contains a `## Tool preference — GitNexus first, Grep/Read fallback` section positioned after `## Output format` and before `## Information gathering — sub-agents`.
- The section lists all four tools, notes that `gitnexus_impact_analysis` is explorer-only, and includes the scout-inheritance note.
- `src/pathly_data/adapters/claude/_meta/explorer.yaml` `tools:` list is `[Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis]`.
- Running `pathly-setup claude --apply` succeeds without error.
- The installed `~/.claude/agents/explorer.md` contains the updated section and frontmatter.

**Delivered by:** Conversation 1, Phase 3.

---

## Story 4 — GitNexus MCP config template exists for each adapter

**Who:** Developer running `pathly-setup <host> --apply` after installing GitNexus.
**What:** A `gitnexus.json` MCP config template is present in each adapter's `_mcp/` directory.
**Why:** Provides the correct `mcpServers` block for each host's config file so that `pathly-setup` can merge it at install time.

**Acceptance criteria:**
- The following files exist with identical content matching the template in `APPROACH.md`:
  - `src/pathly_data/adapters/claude/_mcp/gitnexus.json`
  - `src/pathly_data/adapters/codex/_mcp/gitnexus.json`
  - `src/pathly_data/adapters/copilot/_mcp/gitnexus.json`
  - `src/pathly_data/adapters/antigravity/_mcp/gitnexus.json`
- Each file is valid JSON that parses without error.
- Each file contains exactly the keys: `mcpServers.gitnexus.command` = `"gitnexus"`, `mcpServers.gitnexus.args` = `["mcp"]`, `mcpServers.gitnexus.description` = `"Codebase knowledge graph — query symbols, call chains, and impact analysis"`.

**Delivered by:** Conversation 2, Phase 1.

---

## Story 5 — pathly-setup merges GitNexus MCP config into the host config file

**Who:** Developer running `pathly-setup claude --apply` (or any supported adapter) after GitNexus is installed.
**What:** `pathly-setup` detects `_mcp/gitnexus.json` for the target adapter and deep-merges its `mcpServers` block into the host's MCP config file.
**Why:** Without this step the MCP tools are not exposed to the agent; the developer would have to manually edit their host config.

**Acceptance criteria:**
- `src/install_cli/orchestrate.py` includes an `_run_mcp` function (or equivalent) that reads `_mcp/*.json` files for the adapter, deep-merges the `mcpServers` key into the host config file, and writes the result back.
- The host config target path per adapter is:
  - `claude` → `~/.claude/claude_desktop_config.json` (or `~/.claude/mcp.json` — whichever the APPROACH.md specifies; use `~/.claude/mcp.json`)
  - `codex` → `~/.agents/mcp.json`
  - `copilot` → `.vscode/mcp.json` (workspace-local)
  - `antigravity` → skipped with a printed warning until agy MCP support is confirmed
- `_run_host` in `orchestrate.py` calls `_run_mcp` after agent/skill materialization.
- `install.yaml` for each adapter contains an `mcp:` key with at minimum `destination:` set to the target path above.
- Running `pathly-setup claude --apply --dry-run` prints the MCP config file path that would be written.
- Running `pathly-setup claude --apply` on a machine where `~/.claude/mcp.json` already has other entries does NOT clobber those entries — only the `gitnexus` key is added/updated under `mcpServers`.
- Running `pathly-setup antigravity --apply` prints a warning about unconfirmed MCP support and skips the MCP step without error.

**Delivered by:** Conversation 2, Phases 2–3.

---

## Story 6 — GitNexus tools are available in a live scout session

**Who:** Developer who has run `gitnexus analyze` on the pathly-adapters repo.
**What:** Running a Pathly pipeline task that spawns a scout returns findings that include file:line evidence obtained via `gitnexus_query` or `gitnexus_get_context` rather than only Grep output.
**Why:** Proves the end-to-end wire — MCP installed, tools exposed in the agent frontmatter, agent prompt instructs their use.

**Acceptance criteria:**
- `gitnexus analyze` completes on the pathly-adapters repo without error.
- `pathly-setup claude --apply` runs after Conversation 2 changes without error.
- A manual `/pathly explore` run on a concrete question (e.g., "how does stitch_agent work") returns TRACE.md evidence that references `gitnexus_get_context` or `gitnexus_get_call_chain` in its scout findings section.
- If GitNexus is not installed, the same `/pathly explore` run completes using Grep/Read fallback — no crash, no error about missing tools.

**Delivered by:** Conversation 3.
