# HAPPY_FLOW.md — pathly-studio

_Golden path: developer opens the app, edits a skill, edits a flow, monitors a running pipeline, publishes._

---

## 1. Launch

Developer runs `npm run dev` in `studio/`. Electron window opens at 1280×800.
Sidebar populates instantly: 3 flows, 15 skills, 10 agents, 4 template folders.
`projectPath` is read from `PROJECT_PATH` env var.

## 2. Edit a skill

Developer clicks `go.md` in the Skills section.
Editor panel opens. Config form at top shows: name=go, adapters checked [claude, codex, copilot], tools listed.
Developer unchecks "copilot" adapter. Dot `●` appears next to `go.md` in sidebar.
Developer clicks Edit tab — sees raw markdown. Switches to Preview — sees rendered output.
Developer clicks Split — editor left, preview right, live-synced.
Developer edits a sentence in the markdown. Preview updates instantly.
Developer clicks Save. Dot disappears. File on disk updated.

## 3. Edit a flow

Developer clicks `team.flow.yaml` in the Flows section.
Flow editor opens in Visual tab. Six nodes visible left-to-right: STORMING → PLANNING → BUILDING → REVIEWING → TESTING → DONE. Edges labeled with artifact triggers.
Developer clicks the BUILDING node. Slide-in panel shows agent = "builder". Developer changes it to "builder-v2". Dot appears.
Developer switches to YAML tab — sees the change reflected in raw YAML.
Developer clicks Save. File updated.

## 4. Monitor a running pipeline

Developer selects topic "user-auth-refactor" in the top bar dropdown.
Clicks Monitor in sidebar.
Monitor panel shows: `STORMING ✓  PLANNING ✓  [ BUILDING ]  reviewing  testing  done`
Event log shows last 10 events with timestamps.
Connection badge shows `● HTTP live`.
Developer watches — a new `STATE_TRANSITION` event appears in the log without refreshing.

## 5. Publish

Developer clicks `[↑ Publish]` in the top bar.
Log panel slides up. `pip install -e .` output streams line by line.
"Published successfully" banner appears. Log auto-hides after 3 seconds.
Changes are now live in Claude/Codex.
