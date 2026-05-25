# studio-ui-fixes — Happy Flow

## User opens Monitor for an active topic

1. User selects topic `studio-arch-refactor` in the top bar
2. Monitor reads `pathly/plans/studio-arch-refactor/STATE.json` → `{ current: "BUILDING", flow: "team", ... }`
3. Monitor reads `src/pathly_data/core/flows/team.flow.yaml` → parses `states:` array
4. Pipeline bar renders: `✓ STORMING  ✓ PLANNING  ● BUILDING  reviewing  testing  done`
   - Completed states have green ✓
   - Active state pulses blue
   - Future states are dimmed lowercase
5. Monitor reads `pathly/plans/studio-arch-refactor/EVENTS.jsonl` → parses all events
6. Event log renders rows like:
   ```
   20:52:21   STATE_TRANSITION   STORMING → PLANNING
   20:53:45   STATE_TRANSITION   PLANNING → BUILDING
   ```
   — No "Invalid" timestamps, no empty detail columns

## User opens PLAN section in sidebar

1. Sidebar reads `pathly/plans/studio-arch-refactor/PROGRESS.md`
2. Parser finds `## Conversation Breakdown`, parses exactly that table
3. Sidebar shows:
   ```
   ▼ PLAN [studio-arch-refactor]
     ○ Conv 1 — 1–2  TODO
     ○ Conv 2 — 3–4  TODO
   ```
   — No grep commands, no Phase Detail rows

## User browses a debug session

1. User expands DEBUGS in sidebar
2. Sees: `missing-inputs-in-meta-schema/`, `claude-hooks-not-registered/`, `pathly-fsm-http-connection/`
3. User expands `claude-hooks-not-registered/` → sees `SYMPTOM.md`, `ROOT_CAUSE.md`, `FIX.md`
4. User clicks `ROOT_CAUSE.md` → file opens in editor
