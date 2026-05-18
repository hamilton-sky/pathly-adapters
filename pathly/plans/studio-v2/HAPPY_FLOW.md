# HAPPY_FLOW — studio-v2

This document traces the end-to-end happy path a developer experiences after all
five conversations are complete. Each step maps to a story.

---

## Scenario: Developer runs a debug flow and monitors it in Studio

**Precondition:** Pathly Studio is installed. The developer has a project open at
`C:/dev/myproject`. A debug topic `api-auth` exists at `pathly/debugs/api-auth/`.

---

### Step 1 — Open Studio, see HomeScreen (S5)

Developer launches Studio. HomeScreen scans all three workspace roots.
- `api-auth` appears in the topic list with a `debug` badge.
- A `planning` team topic `onboarding` appears with a `team` badge.
- No `.archive/` topics appear.

**Expected result:** Both topics visible, badges correct.

---

### Step 2 — Sidebar is usable immediately (S3, S4)

Before selecting a topic, developer glances at the Sidebar.
- Section A (Pathly): Flows, Skills, Agents, Templates are all visible even though
  no topic is selected yet.
- Section B (Workspace) shows "(no project)" placeholder — or is empty — because
  no topic is active yet.

**Expected result:** Section A visible. No crash.

---

### Step 3 — Developer selects `api-auth` debug topic

Developer clicks `api-auth` on HomeScreen. Studio sets `activeTopic = "api-auth"`.
- Sidebar Section B now shows Plans, Debugs, Explorations with `api-auth` conversations listed.
- Visual separator between Section A and Section B is visible.

**Expected result:** Two-section Sidebar with correct content in each section.

---

### Step 4 — Monitor opens for the debug topic (S2)

Developer opens the Monitor panel.
- Monitor reads `fsmState.flow = "debug"`.
- Base path resolves to `pathly/debugs/api-auth/`.
- `debug.flow.yaml` is loaded; PIPELINE shows states `SCOPING`, `DIGGING`, `RESOLVING`
  with no `- ` prefix (S1 fix applied).

**Expected result:** Pipeline renders clean state names from the debug flow YAML.

---

### Step 5 — Monitor header shows live context (S6)

Header bar at top of Monitor panel reads:
```
─────────────────────────────────────────────────────────
  Pathly  ·  debug  ·  api-auth
  State : DIGGING    Conv : 2
  Agent : builder
─────────────────────────────────────────────────────────
```
As the FSM transitions, `State` and `Conv` update automatically.

**Expected result:** Header is accurate and live-updating.

---

### Step 6 — Event log timestamps are consistent (S7)

Developer opens the EventLog panel. An AGENT_DONE event is visible.
- The event has a `ts` field — displayed correctly as a time string.
- No event shows `undefined` for its timestamp.

**Expected result:** All events have readable timestamps.

---

### Step 7 — Developer runs a command in the embedded terminal (S8)

Developer presses `Ctrl+\`` to open the terminal panel at the bottom of Studio.
- A new `powershell 1` tab opens; PTY spawns at `C:/dev/myproject`.
- Developer types `dir pathly/debugs/api-auth` — output renders with correct colors.
- Developer clicks `+` to open a second tab — independent shell, same cwd.
- Developer closes the panel; presses `Ctrl+\`` again — tab 1 session is still alive.

**Expected result:** Multi-tab terminal works; sessions survive panel collapse.

---

## End state

All eight stories are verified. The developer has:
- A clean pipeline display for all flow types
- A consistent event log
- A Monitor that routes correctly and shows a live context header
- A two-section Sidebar that is always useful
- A HomeScreen showing all topics
- An embedded terminal they never have to leave
