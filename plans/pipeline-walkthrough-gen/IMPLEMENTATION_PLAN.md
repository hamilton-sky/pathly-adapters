# Implementation Plan: pipeline-walkthrough-gen

## Files to change

1. `src/pathly_data/core/skills/retro.md`
   - Renumber existing steps 4→5, 5→6 (insert new Step 4 before lessons)
   - New Step 4: "Generate pipeline-walkthrough files"
     - Read EVENTS.jsonl (already read in Step 3 — reuse)
     - Get current date and git branch
     - Fill all three templates
     - Write to `pipeline-walkthrough/$ARGUMENTS/`
     - Update the Step 5 report block to include walkthrough paths

2. `src/pathly_data/core/skills/team-flow/retro.md`
   - After writing RETRO.md, add pipeline-walkthrough generation step
   - Same logic: fill templates from EVENTS.jsonl, write to `pipeline-walkthrough/<feature>/`

## Template filling rules

For each placeholder:
- `{{FEATURE}}` — `$ARGUMENTS`
- `{{DATE}}` — today's date (ISO)
- `{{BRANCH}}` — `git branch --show-current`
- `{{USER_INTENT}}` — first HUMAN_RESPONSE value in EVENTS.jsonl, or "not recorded"
- `{{DISCOVERY_TRACE}}` — STATE_TRANSITION events for IDLE/EXPLORING/STORMING states
- `{{CONVERSATION_TRACES}}` — AGENT_DONE events grouped by agent name
- `{{FEEDBACK_LOOP_TABLE}}` — RETRY events or "None"
- `{{FSM_STATES}}` — ordered list of STATE_TRANSITION `to` values
- `{{AGENT_TOKEN_ROWS}}` — AGENT_DONE rows; if all zeros → note "not captured"
- `{{TOTAL_*}}` — aggregated from AGENT_DONE events
- `{{FEEDBACK_FILE_ROWS}}` — files found in `pipeline-walkthrough/<feature>/artifacts/`
- `{{SOURCE_FILE_ROWS}}` — from `git diff --name-only` since branch diverged
- `{{COST_ANALYSIS}}` / `{{RIGOR_VERDICT}}` — omit or note "cost data not captured"

If EVENTS.jsonl does not exist: write files with all placeholders replaced by "not recorded".
