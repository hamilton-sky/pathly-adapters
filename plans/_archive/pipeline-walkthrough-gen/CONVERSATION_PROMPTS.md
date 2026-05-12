# Conversation Prompts: pipeline-walkthrough-gen

## Conv 1 — Add pipeline-walkthrough generation to retro skills

Edit `src/pathly_data/core/skills/retro.md`:
- Insert new Step 4 "Generate pipeline-walkthrough files" between current Step 3 and Step 4
- Renumber old Step 4 → Step 5 and old Step 5 → Step 6
- The new step reads EVENTS.jsonl (already in context from Step 3), fills the three templates,
  and writes to `pipeline-walkthrough/$ARGUMENTS/`
- Update the Step 6 report to include walkthrough output paths

Edit `src/pathly_data/core/skills/team-flow/retro.md`:
- After the RETRO.md write, add pipeline-walkthrough generation
- Same filling logic
