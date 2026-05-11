# User Stories: pipeline-walkthrough-gen

## S1 — Retro generates pipeline-walkthrough files
After `/retro <feature>` completes, `pipeline-walkthrough/<feature>/01-PIPELINE-FLOW.md`,
`02-TOKEN-USAGE.md`, and `03-ARTIFACT-MAP.md` exist with placeholders filled from EVENTS.jsonl.

**Acceptance:** Running retro on a feature that has EVENTS.jsonl produces all three files.

## S2 — Missing token data handled gracefully
If all `cost_usd` are 0.0 in EVENTS.jsonl, the files are still written but token/cost
columns note "not captured" rather than showing zeros.

**Acceptance:** Files are written even when EVENTS.jsonl has no real cost data.

## S3 — team-flow Stage 5 also generates the files
When team-flow routes to RETRO state and writes RETRO.md, it also triggers
pipeline-walkthrough file generation.

**Acceptance:** After a full team-flow pipeline run, all three walkthrough files exist.
