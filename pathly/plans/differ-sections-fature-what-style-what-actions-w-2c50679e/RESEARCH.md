# Research — differ-sections

No external research required. All layers (React/TypeScript components, Electron IPC via `execFile`/`ipcMain`/`ipcRenderer`, Python Flask passthrough, CSS Modules) use established patterns already present in the codebase.

The one open question — the exact `codebase-memory-mcp detect_changes` CLI contract (arg names, output keys) — is local tooling: verify by running `codebase-memory-mcp cli detect_changes --help` or reading the tool source before Conv 4 (backend wiring). No web research can substitute for the actual tool output.
