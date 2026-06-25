# Progress — code-context-injection (Approach B)

Pathly-native code-context injection (runner mode, host-agnostic). Complements the host-MCP
Approach A (gitnexus-integration / lsp-integration). The `cli` backend is independent of A; the
`mcp` backend reuses A's servers, so build it after at least one A plan ships.

| Conversation | Title | Status | Stories |
|---|---|---|---|
| Conv 1 | Provider interface + `none` no-op backend + injection point (safe end-to-end) | TODO | S1, S3 |
| Conv 2 | `cli` backend (blast-radius/callers) + content-hash caching | TODO | S2, S4 |
| Conv 3 | Backend config switch in install/export choice flow + host-agnostic proof | TODO | S5, S6 |
