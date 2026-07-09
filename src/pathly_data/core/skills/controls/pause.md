# pause

This is the canonical, tool-agnostic Pathly behavior for the pause skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Adapter Surface

This core prompt names Pathly workflows, not host commands. Adapters translate
those workflow routes into their native surface.

---

Pause the current session cleanly without losing state.

## Step 1 — Find in-progress feature

Scan `pathly/features/` (skip `.archive/`). For each feature folder, read `STATE.json` if present.
Look for a feature whose `current` state is active (in progress) — not `IDLE`, `DONE`, or a `*_PAUSED` state.

## Step 2 — If a feature is in progress

Read STATE.json for the active feature to get `current_state` and `conv`. Then print
the read-only info panel before writing PAUSED status. Do NOT call next_action.

```
─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  Pausing session.
─────────────────────────────────────────────────────────
```

Then report the pause to the FSM (it persists the paused state — the FSM owns STATE.json):

```
pathly-fsm-call complete-stage --flow pause --topic <feature-name> --project-root <project_root>
```

Where `<feature-name>` is the folder name discovered in Step 1, and `<project_root>` is the current working directory.

Print:

```
Session paused.
Feature: <feature-name>
Tasks done / total: <X> / <Y>   (from the board DAG)

Resume with:  /pathly go
Consult a role: /pathly meet
```

## Step 3 — If no feature is in progress

Print:

```
Nothing in progress. Session closed.

Start fresh with: /pathly start
```
