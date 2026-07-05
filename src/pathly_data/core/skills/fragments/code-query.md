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
- **If `result` is `null`** (the backend is off, or it found nothing), **fall back to Grep/Read** and
  continue — never block on it. This is an accelerator, not a gate.

Use it **before** editing an unfamiliar symbol (check `callers` / `impact` so you don't break a
caller) and whenever a task names a symbol you haven't located yet (`symbol`). Prefer one targeted
query over a broad Grep sweep.
