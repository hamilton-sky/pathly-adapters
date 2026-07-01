# Conversation Prompts — gitnexus-integration

---

## Conversation 1 — Core agent prompt updates + Claude adapter tools lists

**Delivers:** Stories 1, 2, 3
**Pre-conditions:** None

---

You are a builder. Implement Conversation 1 of the gitnexus-integration feature.

### What you are building

Add GitNexus tool-preference sections to three core agent prompts and update the Claude adapter
tool lists so the claude host exposes those tools to the agents.

### Files to edit

**Phase 1 — scout**

Edit `src/pathly_data/core/agents/research/scout.md`.

Insert the following new section between the closing line of `## Output format` (the closing
triple-backtick on the "Ambiguities" block) and the `## Hard constraints — READ ONLY` heading.
Do not modify any existing content.

```
## Code intelligence — preferred tools, Grep/Read fallback

When GitNexus MCP tools are available, prefer them over native tools:
- Find a symbol or pattern         → gitnexus_query          (fallback: Grep)
- Understand callers / callees     → gitnexus_get_context     (fallback: Read + Grep)
- Trace an execution path          → gitnexus_get_call_chain  (fallback: Read chains)
If GitNexus tools are not available, proceed with Grep and Read as normal.
```

Edit `src/pathly_data/adapters/claude/_meta/scout.yaml`.

Replace the existing `tools:` line with:
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain]
```

**Phase 2 — quick**

Edit `src/pathly_data/core/agents/support/quick.md`.

Insert the following new section between the closing line of the `## Role lens` table (the
closing table row for `tester`) and the `## Called by skill orchestrators` heading.

```
## Code intelligence — preferred tools, Grep/Read fallback

Prefer GitNexus tools when available — they count as 1 tool call each:
- Symbol lookup    → gitnexus_query or gitnexus_get_context  (fallback: Grep or Read)
If GitNexus tools are not available, proceed with Grep and Read as normal.
```

Edit `src/pathly_data/adapters/claude/_meta/quick.yaml`.

Replace the existing `tools:` line with:
```yaml
tools: [Read, Glob, Grep, gitnexus_query, gitnexus_get_context]
```

**Phase 3 — explorer**

Edit `src/pathly_data/core/agents/research/explorer.md`.

Insert the following new section between the `---` divider that follows the `## Output format`
table (line 101 in the current file) and the `## Information gathering — sub-agents` heading
(line 103). Insert AFTER the `---` divider on line 101.

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

Edit `src/pathly_data/adapters/claude/_meta/explorer.yaml`.

Replace the existing `tools:` line with:
```yaml
tools: [Read, Glob, Grep, Write, gitnexus_query, gitnexus_get_context, gitnexus_get_call_chain, gitnexus_impact_analysis]
```

**Phase 4 — Propagate and verify**

Run:
```
pathly-setup claude --apply
```

Then verify:
1. Open `~/.claude/agents/scout.md`. The YAML frontmatter must contain all six tools. The body must contain the `## Code intelligence` section.
2. Open `~/.claude/agents/quick.md`. The YAML frontmatter must contain five tools. The body must contain the `## Code intelligence` section.
3. Open `~/.claude/agents/explorer.md`. The YAML frontmatter must contain all eight tools. The body must contain the `## Code intelligence` section.
4. Run `python -m pytest tests/ -q` and confirm it passes.

### Constraints

- Do NOT modify codex, copilot, or antigravity `_meta/` YAML files in this conversation. Those adapters do not use `tools:` lists.
- Do NOT add a `_mcp/` directory in this conversation — that is Conversation 2.
- Do NOT change any other sections of the three agent markdown files beyond the insertion described above.
- After editing core files, always run `pathly-setup claude --apply` to propagate — do not edit `~/.claude/agents/` directly.

---

## Conversation 2 — MCP config templates + pathly-setup stitching

**Delivers:** Stories 4, 5
**Pre-conditions:** Conversation 1 is DONE (all six agent files updated and installed)

---

You are a builder. Implement Conversation 2 of the gitnexus-integration feature.

### What you are building

1. Create `_mcp/gitnexus.json` template files in each adapter directory.
2. Add an `mcp:` section to each adapter's `install.yaml`.
3. Add MCP stitching logic to `src/install_cli/orchestrate.py`.

### Phase 1 — Create _mcp/ template files

Create these four files with identical content:

Files:
- `src/pathly_data/adapters/claude/_mcp/gitnexus.json`
- `src/pathly_data/adapters/codex/_mcp/gitnexus.json`
- `src/pathly_data/adapters/copilot/_mcp/gitnexus.json`
- `src/pathly_data/adapters/antigravity/_mcp/gitnexus.json`

Content (identical for all):
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

Verify: `python -c "import json; json.load(open('src/pathly_data/adapters/claude/_mcp/gitnexus.json'))"` prints no error.

### Phase 2 — Update install.yaml files

Edit `src/pathly_data/adapters/claude/_meta/install.yaml` — add:
```yaml
mcp:
  destination: ~/.claude/mcp.json
```

Edit `src/pathly_data/adapters/codex/_meta/install.yaml` — add:
```yaml
mcp:
  destination: ~/.agents/mcp.json
```

Edit `src/pathly_data/adapters/copilot/_meta/install.yaml` — add:
```yaml
mcp:
  destination: .vscode/mcp.json
  workspace_relative: true
```

Edit `src/pathly_data/adapters/antigravity/_meta/install.yaml` — add:
```yaml
mcp:
  skip: true
  skip_reason: "Antigravity (agy) MCP support not yet confirmed — skipping MCP install step"
```

### Phase 3 — Extend orchestrate.py

File: `src/install_cli/orchestrate.py`

Read the file first. Then add the following new function above `_run_host`:

```python
def _run_mcp(host: str, install_cfg: dict, dry_run: bool) -> None:
    """Deep-merge _mcp/*.json templates into the host's MCP config file."""
    mcp_cfg = install_cfg.get("mcp")
    if not mcp_cfg:
        return
    if mcp_cfg.get("skip"):
        reason = mcp_cfg.get("skip_reason", "MCP step skipped for this adapter")
        print(f"[{host}] MCP: {reason}")
        return

    mcp_dir = adapter_path(host) / "_mcp"
    if not mcp_dir.exists():
        return

    template_files = sorted(mcp_dir.glob("*.json"))
    if not template_files:
        return

    workspace_relative = mcp_cfg.get("workspace_relative", False)
    raw_dest = mcp_cfg["destination"]
    if workspace_relative:
        dest_path = Path.cwd() / raw_dest
    else:
        dest_path = Path(raw_dest).expanduser()

    # Load existing config or start fresh
    if dest_path.exists():
        try:
            existing = json.loads(dest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        existing = {}

    existing_servers = existing.get("mcpServers", {})
    new_servers: dict = {}

    for tmpl_file in template_files:
        tmpl = json.loads(tmpl_file.read_text(encoding="utf-8"))
        new_servers.update(tmpl.get("mcpServers", {}))

    if dry_run:
        keys = list(new_servers.keys())
        print(f"[{host}] MCP (dry-run): would merge {keys} into {dest_path}")
        return

    merged = {**existing_servers, **new_servers}
    existing["mcpServers"] = merged
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[{host}] MCP: merged {list(new_servers.keys())} into {dest_path}")
```

Then inside `_run_host`, add a call to `_run_mcp` immediately after the first `materialize` call
(after the `print(f"[{host}] Wrote {len(written)} file(s) to {dest}")` / nothing-to-write block):

```python
    _run_mcp(host, install_cfg, dry_run)
```

The call must be placed outside any `if dry_run:` guard — `_run_mcp` handles dry-run internally.
Place it after the agent-files materialize block and before the flows materialize block.

### Phase 4 — Verify

Run:
```
pathly-setup claude --apply --dry-run
```
Expected: output includes a line containing `mcp.json` and `gitnexus`.

Run:
```
pathly-setup claude --apply
```
Verify:
- `~/.claude/mcp.json` exists.
- `python -c "import json,pathlib; d=json.loads(pathlib.Path.home().joinpath('.claude/mcp.json').read_text()); print(d['mcpServers']['gitnexus'])"` prints the gitnexus entry.
- If you had pre-existing entries in `~/.claude/mcp.json`, confirm they are still present.

Run:
```
pathly-setup antigravity --apply
```
Verify: output contains the skip_reason message. No traceback.

Run:
```
python -m pytest tests/ -q
```
All tests pass.

### Constraints

- Do NOT modify the `materialize()` function or the manifest logic.
- Do NOT modify any agent or skill markdown files in this conversation.
- `_run_mcp` must never clobber pre-existing `mcpServers` keys that are not in the template.
- The antigravity adapter must NOT attempt to write any MCP file — print the skip reason and return.

---

## Conversation 3 — End-to-end smoke test

**Delivers:** Story 6
**Pre-conditions:** Conversations 1 and 2 are DONE. GitNexus package available to install.

---

You are a builder. Implement Conversation 3 of the gitnexus-integration feature.

### What you are doing

Verify the full end-to-end GitNexus integration works on this repo. This conversation is
verification-only — it does not produce source code changes unless a gap is found.

### Phase 1 — Install GitNexus

Determine the correct install command for GitNexus (check https://github.com/abhigyanpatwari/GitNexus
for the current install method — likely `npm install -g gitnexus` or `pip install gitnexus`).

Run:
```bash
gitnexus analyze
```
in the `pathly-adapters` repo root. If `gitnexus` is not on PATH, resolve the PATH issue first.

Verify: command exits 0. Confirm a knowledge graph is built (look for any output mentioning
files parsed, nodes created, or a similar success indicator).

### Phase 2 — Run pathly-setup to install the MCP config

```bash
pathly-setup claude --apply
```

Verify `~/.claude/mcp.json` contains a `mcpServers.gitnexus` block with `"command": "gitnexus"`.

### Phase 3 — Run a live explore task

Invoke:
```
/pathly explore
```

Use the question: "How does `stitch_agent` in `src/install_cli/stitch.py` produce the final
agent markdown file — what is the exact sequence of sections it assembles?"

After the explore run completes, read `pathly/explorations/*/TRACE.md` (the most recently
created exploration).

Acceptance check:
- At least one finding in the trace references output from `gitnexus_get_context` or
  `gitnexus_get_call_chain` (look for tool call evidence in the scout findings or trace body).
- The trace correctly identifies the three-section assembly in `stitch_agent`: frontmatter block,
  core body, optional footer.

### Phase 4 — Verify graceful fallback

Rename `~/.claude/mcp.json` temporarily:
```bash
mv ~/.claude/mcp.json ~/.claude/mcp.json.bak
```

Run the same `/pathly explore` question again.

Verify:
- No error about missing tools or unavailable MCP server.
- A TRACE.md is still produced.
- The trace uses Grep/Read evidence (no gitnexus tool references).

Restore:
```bash
mv ~/.claude/mcp.json.bak ~/.claude/mcp.json
```

### Phase 5 — Record outcome

If all phases pass, update `pathly/plans/gitnexus-integration/PROGRESS.md` — mark Conversation 3
as DONE and add a one-line smoke-test note.

If any phase fails, write the failure details to
`pathly/plans/gitnexus-integration/feedback/SMOKE_TEST_FAILURES.md` and leave Conversation 3
as TODO.

### Constraints

- Do NOT edit source code unless a genuine bug is found (misconfigured MCP key name, wrong tool
  name in YAML, etc.). If a bug is found, fix it, re-run `pathly-setup claude --apply`, and
  re-run the affected phase before marking DONE.
- Do NOT modify the explore skill, FSM, or any orchestrator code.
- This conversation is complete only when all four phases produce their expected outcomes.
