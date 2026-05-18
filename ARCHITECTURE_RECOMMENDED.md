# Pathly — Recommended Architecture

Author: Claude Code review  
Date: 2026-05-18  
Scope: Full system — backend, orchestration, Studio UI, and host adapters

---

## 1. Current Architecture (What Exists Today)

```
┌─────────────────────────────────────────────────────────┐
│  pathly-adapters (Python package, pip install)          │
│                                                         │
│  install_cli/        → detects hosts, stitches files,  │
│                         materializes to ~/.claude/ etc. │
│  pathly_data/        → source-of-truth content          │
│    core/             → tool-agnostic agents + skills    │
│    adapters/         → thin per-host wrappers           │
│  pathly_orchestrator/→ FSM engine, MCP + HTTP servers  │
│  pathly_hooks/       → post-tool-use hook scripts       │
│  pathly_telemetry/   → token/cost reporting             │
│  pathly_studio_cli/  → downloads Studio desktop binary  │
└─────────────────────────────────────────────────────────┘
         │ installs to
         ▼
┌──────────────────────────────────────────────┐
│  Host AI Tools                               │
│  Claude Code  │  Codex  │  Copilot/VS Code  │
└──────────────────────────────────────────────┘
```

**What works well:**
- Core/adapter separation keeps content host-neutral
- Stitch pipeline is deterministic and auditable
- Atomic install with manifest-based rollback
- FSM is LLM-free (pure Python, testable in isolation)
- MCP + HTTP dual interface for the FSM is flexible

**What needs work:**
- Studio UI (separate binary, opaque from this repo)
- No observability into running workflows from outside the CLI
- No shared internal utilities (path discovery duplicated)
- Missing tests for rollback, manifests, hooks

---

## 2. Recommended Architecture

### 2.1 Package Boundaries (Keep)

Keep the current package boundaries. They are well-drawn:

```
pathly-adapters           ← install + content (what you have now)
pathly-studio             ← desktop UI (separate repo, separate binary)
```

Do not merge them. The installer and the UI have different release cadences and different distribution channels (PyPI vs GitHub Releases).

---

### 2.2 Internal Module Reorganization

Add one shared internal module to eliminate CLI duplication:

```
src/pathly_orchestrator/
  _discovery.py       ← NEW: SCAN_ROOTS, find_most_recent_state, find_topic_dir
  _events_io.py       ← NEW: safe EVENTS.jsonl read/write with corrupt-line handling
  fsm.py
  mcp_server.py
  http_server.py
  eventlog.py
  runner.py
  back_cli.py         ← imports from _discovery
  ff_cli.py           ← imports from _discovery
  status_cli.py       ← imports from _discovery
  log_cli.py          ← imports from _discovery
```

---

### 2.3 FSM Hardening (Priority)

The FSM is the most critical runtime component. Recommended additions:

1. **Timeouts** on all subprocess calls (git, Codex CLI)
2. **Idempotent state writes** — write STATE.json only if the state actually changed
3. **Event schema** — add a `_schema_version: 1` field to every EVENTS.jsonl entry so readers can handle future format changes
4. **Corrupt-line tolerance** — wrap all EVENTS.jsonl reads in try/except per line

---

### 2.4 Future Adapters (When Demand Exists)

```
src/pathly_data/adapters/
  claude/       ✅ done
  codex/        ✅ done
  copilot/      ✅ done
  cursor/       → when demanded (cursor.rules + MCP config)
  windsurf/     → when demanded (windsurf.rules)
  bmad/         → when demanded (chat mode definitions)
  generic/      → copy-paste prompt pack (no installer needed)
```

Rule: keep adapters thin. Any logic that belongs to more than one adapter belongs in `core/`.

---

### 2.5 CI Gates to Add

```yaml
# .github/workflows/ci.yml (additions)
- pytest tests/test_manifests.py          # schema-validate all 3 plugin manifests
- pytest tests/test_rollback.py           # partial-failure rollback regression
- pytest tests/test_hooks.py              # hook path validation + edge cases
- pytest tests/test_stitch.py             # stitch output determinism + no user input
```

---

## 3. Studio UI Recommendation

### 3.1 Should You Use MUI or LangSmith-style?

**Short answer: Neither MUI nor "LangSmith-style" as a library — use shadcn/ui + Tailwind CSS + Base UI primitives.**

---

### 3.2 Why Not MUI

| Concern | Detail |
|---------|--------|
| Look and feel | MUI's Material Design aesthetic signals "consumer app," not "developer tool." Your users are engineers who use Cursor, Linear, and VS Code — tools that look nothing like MUI. |
| Bundle size | MUI uses CSS-in-JS (Emotion) at runtime, adding ~50 KB gzipped to every page. Developer tools are judged on perceived speed. |
| Theming difficulty | Getting a dense, dark, IDE-adjacent theme out of MUI requires fighting the library. The default dark mode still looks like Google's products. |
| When MUI is right | MUI X's DataGrid is best-in-class for heavy tabular data (eval results, trace tables). You can adopt it as a standalone component even in a shadcn codebase. |

---

### 3.3 Why Not "LangSmith-style" (as a library)

LangSmith is not a component library — it is a product with a design language. What makes LangSmith look good is its use of **Tailwind CSS + shadcn/ui**, which is exactly what you should adopt.

---

### 3.4 Recommended Stack: shadcn/ui + Tailwind + Base UI

```
┌─────────────────────────────────────────────────────┐
│  Pathly Studio UI Stack                             │
│                                                     │
│  shadcn/ui components  (copy-owned, not a dep)     │
│  Tailwind CSS 4.x      (utility-first styling)     │
│  Base UI primitives    (accessibility, keyboard nav)│
│  Tremor                (charts and metric cards)    │
│  MUI X DataGrid        (trace/eval tables only)     │
└─────────────────────────────────────────────────────┘
```

**Why this stack:**

| Reason | Detail |
|--------|--------|
| Industry consensus | Linear, Vercel, LangSmith ecosystem all use shadcn/ui + Tailwind |
| AI code generation friendly | shadcn components live in your codebase as source files — Claude Code can read, modify, and generate them |
| Owned, not locked in | shadcn/ui is "copy it, own it" — no npm version lock, no vendor API |
| Accessibility | Base UI (the new primitive layer shadcn supports) provides battle-tested ARIA, keyboard nav, focus management for free |
| Dark-first | Tailwind makes dark mode a first-class citizen — `dark:` prefix is the standard, not an afterthought |
| Radix note | Shadcn originally used Radix UI primitives. In 2026 Radix maintenance has slowed; shadcn now supports Base UI (by the MUI team) as an alternative primitive. Initialize new components with Base UI. |

---

### 3.5 Design System Guidance for Pathly Studio

Pathly Studio should look and feel like a **developer workflow tool**, not a consumer dashboard:

**Palette:**
- Background: near-black (`zinc-950` or `#0a0a0a`)
- Surface: `zinc-900` / `zinc-800` for cards and panels
- Accent: a single brand color for active states and CTAs (blue or indigo)
- Text: `zinc-100` for primary, `zinc-400` for secondary/muted

**Typography:**
- Monospace for all agent output, state labels, file paths (`font-mono`)
- System sans for UI text (`font-sans`, Inter or system-ui)

**Density:**
- Compact by default (this is a tool, not a marketing page)
- Data tables and logs should show as many rows as fit
- Sidebars are the primary navigation pattern (not top-nav tabs)

**Component priorities for first build:**
1. FSM state timeline (current stage, progress, transitions)
2. Event log viewer (EVENTS.jsonl rendered as a live feed)
3. Feedback file viewer (IMPL_QUESTIONS.md, HUMAN_QUESTIONS.md)
4. Topic/flow selector sidebar
5. Telemetry summary (token cost per conversation)

---

### 3.6 Electron vs Web vs Tauri

For Pathly Studio (the desktop binary):

| Option | Recommendation |
|--------|---------------|
| Electron | Easiest to ship cross-platform with Node.js access to filesystem + subprocess. Mature ecosystem. Heavy (~150 MB). Acceptable for a dev tool used daily. |
| Tauri | ~10 MB binary, Rust backend, webview frontend. Better memory usage. Slightly more complex to set up. Best long-term choice if you want a lean binary. |
| Web-only | Simplest to start: `vite + react` served from `pathly-fsm-http`. No download required. Can always shell into Electron/Tauri later. Good for MVP. |

**Recommendation:** Start with a web UI served by `pathly-fsm-http` (already running at `127.0.0.1:8765`). Ship it as a browser-openable URL first. Wrap in Tauri when you need native filesystem access or a system-tray entry.

---

## 4. Where the HTTP Server Fits

The existing `pathly-fsm-http` Flask server is already the right integration point for a web UI:

```
Pathly Studio (React + shadcn/ui)
  │
  │ POST /next_action         → advance FSM
  │ POST /complete_stage      → complete current stage
  │ GET  /health              → liveness
  │ GET  /events/stream       → SSE live event feed
  │
  ▼
pathly-fsm-http (Flask, 127.0.0.1:8765)
  │
  ▼
pathly_orchestrator.fsm  (pure Python FSM)
  │
  ▼
STATE.json + EVENTS.jsonl (project plans/ directory)
```

**Before serving a UI from this server**, apply the security fixes from ANALYSIS.md #3 (validate `project_root` in SSE endpoint) and #15 (clean up tailer threads on disconnect).

---

## 5. Recommended Next Steps (Priority Order)

1. **Security hardening** — fix items #1, #2, #3 from ANALYSIS.md (hook paths, manifest integrity, SSE path validation)
2. **Add missing tests** — rollback, hooks, manifests, stitch determinism
3. **Extract `_discovery.py`** — eliminate CLI duplication
4. **Fix `datetime.utcnow()`** — one-line fix, eliminates deprecation warnings on Python 3.12+
5. **Add git subprocess timeouts** — prevents FSM hangs
6. **Ship a minimal web UI** — shadcn/ui + Tailwind served from existing HTTP server
7. **Add Cursor/Windsurf adapters** — when there is real user demand
