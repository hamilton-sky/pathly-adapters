# Implementation Plan — gitnexus-integration

## Overview

Give Pathly's read-only research agents (scout, quick, explorer) first-class access to the
GitNexus MCP knowledge graph. Two delivery phases: (1) update agent prompts and adapter tool
lists so agents know to use GitNexus tools and Claude exposes them; (2) create MCP config
templates per adapter and extend `pathly-setup` to stitch them into host MCP config files.
A third conversation verifies the full wire end-to-end.

---

## Conversation 1 — Core agent prompt updates + Claude adapter tools lists

**Delivers:** Stories 1, 2, 3

**Pre-conditions:** None. All edits are to source files under version control.

### Phase 1 — scout.md + claude scout.yaml

Files:
- `src/pathly_data/core/agents/research/scout.md`
- `src/pathly_data/adapters/claude/_meta/scout.yaml`

Changes:
1. In `scout.md`, insert a new `## Tool preference — GitNexus first, Grep/Read fallback` section between the closing line of `## Output format` and the `## Hard constraints — READ ONLY` heading. Use the exact block from `APPROACH.md`:
   - `gitnexus_query` → fallback: Grep
   - `gitnexus_get_context` → fallback: Read + Grep
   - `gitnexus_get_call_chain` → fallback: Read chains
   - Closing note: if GitNexus tools are not available, proceed with Grep and Read as normal.
2. In `scout.yaml`, update the `tools:` list to:
   `tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain]`

### Phase 2 — quick.md + claude quick.yaml

Files:
- `src/pathly_data/core/agents/support/quick.md`
- `src/pathly_data/adapters/claude/_meta/quick.yaml`

Changes:
1. In `quick.md`, insert a new `## Tool preference — GitNexus first, Grep/Read fallback` section between the closing line of `## Role lens` table and the `## Called by skill orchestrators` heading. Content from `APPROACH.md`:
   - Note that GitNexus calls count as 1 tool call each.
   - `gitnexus_query` or `gitnexus_get_context` → fallback: Grep or Read
   - Closing note: if not available, proceed with Grep and Read as normal.
2. In `quick.yaml`, update the `tools:` list to:
   `tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context]`

### Phase 3 — explorer.md + claude explorer.yaml

Files:
- `src/pathly_data/core/agents/research/explorer.md`
- `src/pathly_data/adapters/claude/_meta/explorer.yaml`

Changes:
1. In `explorer.md`, insert a new `## Tool preference — GitNexus first, Grep/Read fallback` section between the closing `---` divider after `## Output format` and the `## Information gathering — sub-agents` heading. Content from `APPROACH.md`:
   - `gitnexus_query` for symbol/pattern search
   - `gitnexus_get_context` for understanding a function
   - `gitnexus_get_call_chain` for tracing execution paths
   - `gitnexus_impact_analysis` for blast-radius (note: only explorer uses this)
   - Scout inheritance note
   - Closing note: if not available, proceed with Glob, Grep, Read as normal.
2. In `explorer.yaml`, update the `tools:` list to:
   `tools: [Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis]`

### Phase 4 — Propagate + verify

Run:
```
pathly-setup claude --apply
```

Verify:
- `~/.claude/agents/scout.md` frontmatter contains all six tool names and body contains `## Tool preference` section.
- `~/.claude/agents/quick.md` frontmatter contains five tool names and body contains `## Tool preference` section.
- `~/.claude/agents/explorer.md` frontmatter contains all eight tool names and body contains `## Tool preference` section.
- `python -m pytest tests/ -q` passes.

**Note on codex/copilot/antigravity:** These adapters do NOT use `tools:` lists in their `_meta/` YAMLs. Do not add GitNexus tools to those adapters in this conversation — the core prompt change propagates to all adapters via their agent files, but tool exposure is Claude-only.

---

## Conversation 2 — MCP config templates + pathly-setup stitching

**Delivers:** Stories 4, 5

**Pre-conditions:** Conversation 1 is DONE.

### Phase 1 — Create _mcp/ template directories and gitnexus.json files

Create the following files, all with identical content:

```
src/pathly_data/adapters/claude/_mcp/gitnexus.json
src/pathly_data/adapters/codex/_mcp/gitnexus.json
src/pathly_data/adapters/copilot/_mcp/gitnexus.json
src/pathly_data/adapters/antigravity/_mcp/gitnexus.json
```

Content (identical for all four):
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

### Phase 2 — Update install.yaml files with mcp: destination

Add an `mcp:` block to each adapter's `install.yaml`:

- `src/pathly_data/adapters/claude/_meta/install.yaml`:
  ```yaml
  mcp:
    destination: ~/.claude/mcp.json
  ```

- `src/pathly_data/adapters/codex/_meta/install.yaml`:
  ```yaml
  mcp:
    destination: ~/.agents/mcp.json
  ```

- `src/pathly_data/adapters/copilot/_meta/install.yaml`:
  ```yaml
  mcp:
    destination: .vscode/mcp.json
    workspace_relative: true
  ```

- `src/pathly_data/adapters/antigravity/_meta/install.yaml`:
  ```yaml
  mcp:
    skip: true
    skip_reason: "Antigravity (agy) MCP support not yet confirmed"
  ```

### Phase 3 — Extend orchestrate.py with MCP stitching logic

File: `src/install_cli/orchestrate.py`

Add a new helper function `_run_mcp(host, install_cfg, dry_run)`:

- Reads `mcp:` from `install_cfg`. If absent or `skip: true`, print the `skip_reason` if present and return immediately.
- Resolves the `_mcp/` directory: `adapter_path(host) / "_mcp"`. If directory does not exist, return silently.
- For each `*.json` in `_mcp/`, parse the JSON and deep-merge its `mcpServers` block into the target config file.
- Deep merge rule: existing `mcpServers` entries not named in the template are preserved. The template's entries are added or overwritten.
- `destination` path: expand `~` with `Path.expanduser()`. For `workspace_relative: true` destinations, resolve relative to `Path.cwd()`.
- If the destination file does not exist yet, create it with the template's content as the initial value (wrap in a top-level `{"mcpServers": {...}}`).
- If `dry_run=True`, print the destination path and the keys that would be merged under `mcpServers` — do NOT write.
- Call `_run_mcp` inside `_run_host` immediately after the `materialize` call for agent files.

### Phase 4 — Test the MCP stitching

Run:
```
pathly-setup claude --apply --dry-run
```
Expected output includes a line naming `~/.claude/mcp.json` and the `gitnexus` key.

Run:
```
pathly-setup claude --apply
```
Verify `~/.claude/mcp.json` exists and contains a valid `mcpServers.gitnexus` block. Verify any pre-existing `mcpServers` entries are still present.

Run:
```
pathly-setup antigravity --apply
```
Verify the MCP step prints the skip warning and exits cleanly.

Run:
```
python -m pytest tests/ -q
```
All tests pass.

---

## Conversation 3 — End-to-end smoke test

**Delivers:** Story 6

**Pre-conditions:** Conversations 1 and 2 are DONE. GitNexus is installable via npm/pip.

### Phase 1 — Install GitNexus and analyze the repo

```bash
npm install -g gitnexus          # or pip install gitnexus — verify correct package
gitnexus analyze                 # run in pathly-adapters root
```

Verify: no error. Confirm `gitnexus mcp --help` (or `gitnexus mcp`) prints usage or starts a stdio server.

### Phase 2 — Run a Pathly explore task with GitNexus active

Invoke `/pathly explore` on a concrete structural question such as:
"How does `stitch_agent` in `src/install_cli/stitch.py` produce the final agent markdown file?"

Check TRACE.md:
- At least one finding references a GitNexus tool call (`gitnexus_get_context` or `gitnexus_get_call_chain`).
- The trace contains file:line evidence consistent with the actual code path in `stitch.py`.

### Phase 3 — Verify graceful fallback

Temporarily rename `~/.claude/mcp.json` to `~/.claude/mcp.json.bak` to simulate GitNexus absent.
Re-run the same explore task. Verify:
- No crash, no error about missing tools.
- TRACE.md is still produced using Grep/Read evidence.
Restore `~/.claude/mcp.json.bak` to `~/.claude/mcp.json`.

---

## Decisions made during planning

| Decision | Rationale |
|---|---|
| codex/copilot/antigravity do not receive `tools:` list additions | Those adapters do not use the `tools:` YAML field — no host enforcement of tool lists. Core prompt change alone propagates GitNexus preference via the agent markdown. |
| antigravity MCP step is skipped with a warning | agy CLI MCP support is unconfirmed per APPROACH.md. Skipping prevents a broken install while keeping the template ready. |
| cursor adapter is out of scope | Cursor does not yet exist in this repo. Adding it is a separate initiative. |
| Deep-merge, not overwrite | Users may have other MCP servers configured. Clobbering their config is unacceptable. |
| copilot MCP destination is workspace-relative | VSCode MCP config is project-local (`.vscode/mcp.json`), not a global file. |
