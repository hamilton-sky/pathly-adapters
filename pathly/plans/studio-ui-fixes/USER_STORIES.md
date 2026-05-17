# studio-ui-fixes — User Stories

## S1: Event log shows correct timestamps and transition detail

**As a** user watching the Monitor,
**I want** the event log to show readable timestamps and what state changed to what,
**So that** I can understand what happened and when without guessing.

### Acceptance criteria
- All events show a timestamp in `HH:MM:SS` format; events without a `ts` field show `—` instead of "Invalid"
- `STATE_TRANSITION` events show `FROM → TO` (e.g., `PLANNING → BUILDING`) in the detail column
- Events with a `reason` field but no `from`/`to` show the reason string in the detail column
- Events with none of the above show an empty detail column (no crash, no "undefined")

---

## S2: Pipeline bar reflects the actual flow's states

**As a** user watching the Monitor,
**I want** the pipeline bar to show the real stages of the active flow,
**So that** states like TESTING and RETRO are visible and COMMITTING is not shown when it is not part of the flow.

### Acceptance criteria
- Pipeline bar states are loaded from the flow YAML named in `fsmState.flow`, not a hardcoded list
- States appear in the order defined in the flow YAML `states:` array
- When the flow YAML cannot be read, the pipeline falls back to a sensible default set and does not crash
- When `fsmState` is `null`, the pipeline shows all states dimmed (idle state, same as before)

---

## S3: Sidebar PLAN section shows clean conversation names

**As a** user looking at the sidebar,
**I want** the PLAN section to list conversations with their real title and status,
**So that** I am not reading grep commands as status values.

### Acceptance criteria
- Each row in the PLAN section comes from the "Conversation Breakdown" table in PROGRESS.md only
- The title column shows the Phases value (e.g., `1–2`), not the Verify command
- The status column shows `TODO`, `IN_PROGRESS`, or `DONE`, not command text
- Phase Detail rows (e.g., `1.1`, `1.2`) are not shown in the sidebar

---

## S4: Sidebar shows debugs and explorations

**As a** user,
**I want** the sidebar to list my debug and exploration sessions,
**So that** I can open SYMPTOM.md, ROOT_CAUSE.md, etc. without leaving the studio.

### Acceptance criteria
- A DEBUGS section appears in the sidebar listing subfolder names from `pathly/debugs/`
- An EXPLORATIONS section appears listing subfolder names from `pathly/explorations/`
- Expanding a subfolder shows its files; clicking a file opens it in the editor
- Sections are hidden if the directory does not exist (no crash)
