# PROGRESS — pathly-studio

| Conv | Title | Stories | Status |
|------|-------|---------|--------|
| 1 | Electron scaffold + sidebar | S1, S2 | DONE |
| 2 | Editor panel | S3 | DONE |
| 3 | Flow editor | S4 | DONE |
| 4 | Live monitor + Publish | S5, S6 | DONE |

## Verified in codebase

| Phase | File | Status |
|-------|------|--------|
| 1.1–1.7 | `studio/` scaffold, `main/index.ts`, `preload/index.ts`, `HomeScreen.tsx`, `Sidebar.tsx`, `App.tsx`, `store/` | DONE |
| 2.1–2.5 | `services/`, `Editor/index.tsx`, `Editor/ConfigForm.tsx`, `Editor/MarkdownEditor.tsx`, `Editor/MarkdownPreview.tsx` | DONE |
| 3.1–3.3 | `FlowEditor/index.tsx`, `FlowEditor/VisualView.tsx`, `FlowEditor/YamlView.tsx` | DONE |
| 4.1–4.7 | `TopBar.tsx`, `Monitor/index.tsx`, `Monitor/FsmView.tsx`, `Monitor/EventLog.tsx`, `ipc/fs.ts`, `ipc/watcher.ts`, `ipc/http.ts`, `ipc/shell.ts` | DONE |

**Prerequisites:**
- Node.js 18+ and npm installed on the build machine.
- Conv 4 additionally requires: http-fsm-driver Conv 1 DONE (`get_fsm_state` and `get_events` HTTP tools must exist in `http_server.py` before the live monitor can connect).
**Follow-up:** `pathly-studio-part-2` — packaging (electron-builder), auto-update, install wizard.
