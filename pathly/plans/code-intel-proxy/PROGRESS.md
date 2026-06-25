# Progress — code-intel-proxy (Approach C)

Pathly as the code-intelligence gateway (HTTP proxy on the FSM server; interactive + runner; all
agents). Shares the `runner/code_context` backend with Approach B (code-context-injection) — build
the shared backend once. Complements host-MCP Approach A (gitnexus/lsp).

| Conversation | Title | Status | Stories |
|---|---|---|---|
| Conv 1 | Reachability prereq + `POST /code/query` route over shared backend | TODO | S1, S2 |
| Conv 2 | `pathly-fsm-call code-query` shim + gateway cache/logging/routing | TODO | S3, S4 |
| Conv 3 | Capability control (fragment + endpoint permission) + advertise to all roles | TODO | S5, S7 |
| Conv 4 | (Optional) `pathly-code` MCP shim republishing typed tools | TODO | S6 |
