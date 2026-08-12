# Progress — semantic-code-search

Adds a third `/code/query` engine (`semantic`) for meaning-based code search — the code-intel gap
vs. the industry (Sourcegraph/Cody/CocoIndex-style embedding search). Additive to the existing
`graph`/`lsp` engines; reuses `runner/embeddings.py` + sqlite-vec. Backend-only for v1.

| Conversation | Title | Status | Stories |
|---|---|---|---|
| Conv 1 | `code_embeddings` table + `SemanticProvider` skeleton (safe-off) | TODO | S1 |
| Conv 2 | Incremental code indexer (line-window v1, content-hash) | TODO | S2 |
| Conv 3 | Gateway wiring (`engine=semantic` + `search` op) + reindex seam | TODO | S3, S4 |
| Conv 4 | End-to-end smoke test + `tests/code_intel/` suite | TODO | S5 |
