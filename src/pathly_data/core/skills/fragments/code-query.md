## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" -d '{
  "op": "symbol",
  "target": "<file path OR symbol name>",
  "role": "<your-role>",
  "scope": "<feature>" }'
```

- `op` — `symbol` (definition + signature) · `callers` (who calls it) · `impact` (what a change to
  it touches) · `chain` (call path between two symbols) · `context` (surrounding structure) ·
  `pattern` (find a code pattern). Your `role` gates which ops you may use.
- The response is `{ "ok": true, "result": <block-or-null>, "backend": "<name>" }`.
- **If `result` is `null`** (backend off, file not yet indexed, or path unresolved), first try the
  **direct-CLI fallback** below; then fall back to Grep/Read. Never block on it — an accelerator, not a gate.

### Direct-CLI fallback (proxy returned null)

If `codebase-memory-mcp` is on the PATH, query its pre-built code graph directly — this works in
headless runs and covers cases the proxy misses (e.g. a file added since the last index). Resolve the
project slug once, then search:

```bash
codebase-memory-mcp cli list_projects '{}'    # pick the project whose root_path is your repo → use its "name"
codebase-memory-mcp cli search_code '{"project":"<name>","pattern":"<symbol_or_text>"}'   # ranked; note: pattern, not query
codebase-memory-mcp cli query_graph '{"project":"<name>","query":"MATCH (n) WHERE n.name=\"<sym>\" RETURN n.name, n.file_path"}'
```

`search_code` takes `pattern` (grep-like over the graph); `query_graph` runs Cypher (callers/callees,
call paths, impact). If the binary is absent or returns nothing, fall back to Grep/Read.

Use it **before** editing an unfamiliar symbol (check `callers` / `impact` so you don't break a
caller) and whenever a task names a symbol you haven't located yet (`symbol`). Prefer one targeted
query over a broad Grep sweep.
