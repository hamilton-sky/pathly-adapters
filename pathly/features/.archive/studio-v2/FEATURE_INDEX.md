# FEATURE_INDEX — studio-v2

**Product:** Pathly Studio (Electron + React)
**Rigor:** standard
**Started:** 2026-05-18

---

## What this feature delivers

A set of targeted improvements to Pathly Studio that make it usable for all three
flow types (team, debug, explore), fix known display bugs, restructure the sidebar
into a coherent two-section layout, and add an embedded terminal panel so users
never need to leave the app to run commands.

---

## Story index

| ID | Title | Conversation | Status |
|----|-------|-------------|--------|
| S1 | Fix pipeline display in Monitor | Conv 1 | pending |
| S7 | EVENTS.jsonl timestamp standardization | Conv 1 | pending |
| S2 | Monitor supports all flow types | Conv 2 | pending |
| S6 | Contextual panel header in Monitor | Conv 2 | pending |
| S3 | Sidebar: always show Pathly-installed sections | Conv 3 | pending |
| S4 | Sidebar: two-section structure | Conv 3 | pending |
| S5 | HomeScreen scans all three workspace roots | Conv 4 | pending |
| S8 | Terminal panel (VS Code-style) | Conv 5 | pending |

---

## Conversation index

| Conv | Title | Stories | Status |
|------|-------|---------|--------|
| 1 | Quick fixes | S1, S7 | pending |
| 2 | Monitor improvements | S2, S6 | pending |
| 3 | Sidebar restructure | S3, S4 | pending |
| 4 | HomeScreen all flows | S5 | pending |
| 5 | Terminal panel | S8 | pending |

---

## Layers touched

| Layer | Files | Conversations |
|-------|-------|---------------|
| Renderer — Monitor | `studio/src/renderer/src/components/Monitor/index.tsx` | 1, 2 |
| Renderer — Sidebar | `studio/src/renderer/src/components/Sidebar/index.tsx` | 3 |
| Renderer — HomeScreen | `studio/src/renderer/src/components/HomeScreen/index.tsx` | 4 |
| Renderer — hooks | `studio/src/renderer/src/hooks/useProjectFiles.ts` | 3, 4 |
| Renderer — App/TopBar | `studio/src/renderer/src/App.tsx`, `studio/src/renderer/src/components/TopBar/index.tsx` | 5 |
| Main process | `studio/src/main/index.ts` | 5 |
| IPC bridge | `studio/src/preload/index.ts` | 5 |
| Python FSM | `src/pathly_orchestrator/runner.py` | 1 |

---

## Out of scope

- Cost telemetry from Agent tool invocations
- `pathly-run` standalone CLI improvements
- Changes to Python FSM engine or flow YAMLs (except runner.py timestamp fix)
