# simplify-review — Artifact Map

**Date:** 2026-05-13

## Feedback File Archive

| File | Written by | Resolved by | Outcome |
|---|---|---|---|
| REVIEW_FAILURES_conv1_attempt1.md | reviewer | builder (conv 1 fix) | Broken relative link corrected |

## Source Files Changed

| File | Story ref | What changed |
|---|---|---|
| `README.md` | S1.2 | Added FLOW_DIAGRAM.md link; /start equivalence tip; split claude hosts row; fixed _meta path; added Copilot skills destination |
| `docs/ARCHITECTURE.md` | S1.1 | Replaced detailed skill listing with compact tree + FLOW_DIAGRAM.md link |
| `docs/FLOW_DIAGRAM.md` | S1.3 | Added Copilot mermaid branch; added verify→verify-state footnote; added Copilot invocation examples block |
| `docs/PATHLY_ARCHITECTURE.md` | S1.1, S1.4 | Added scope note with FLOW_DIAGRAM.md link; fixed pip install command |
| `schemas/pathly-meta.schema.json` | S2.1 | Added natural_language, telemetry, hooks, variables, templates, status; full description annotations; host enum; hooks required/enum |
| `src/pathly_data/schemas/pathly-meta.schema.json` | S2.1 | Synced with root; added required, enum, minLength, description throughout |
