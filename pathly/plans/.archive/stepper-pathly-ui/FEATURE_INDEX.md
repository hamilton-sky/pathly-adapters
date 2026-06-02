# Feature: stepper-pathly-ui

Add Electron/CDP support to the Playwright Stepper framework and wire up Pathly Studio as its first Electron test site, enabling repeatable UI smoke and regression flows against the real Electron renderer.

## Repos involved

| Repo | Path | Role |
|---|---|---|
| Stepper framework | `C:\Users\Yafit\playwright-stepper-framework\` | CDP launcher, POMs, glue actions, workflows |
| Pathly Studio | `C:\Users\Yafit\pathly-adapters\studio\` | `data-testid` attributes added to renderer components |

## Conversation list

| Conv | Title | Repo | Status |
|---|---|---|---|
| 1 | Electron CDP launcher | playwright-stepper-framework | TODO |
| 2 | data-testid attributes in Studio | pathly-adapters/studio | TODO |
| 3 | Pathly POMs | playwright-stepper-framework | TODO |
| 4 | Pathly glue actions + register | playwright-stepper-framework | TODO |
| 5 | Pathly workflows + smoke test | playwright-stepper-framework | TODO |

## Dependency order

Conv 1 (CDP launcher) must complete before Conv 3, 4, 5 — it is the unblocking primitive.
Conv 2 (data-testids) must complete before Conv 3 — POMs depend on stable testid names.
Conv 3 (POMs) must complete before Conv 4 — glue imports POMs.
Conv 4 (glue + register) must complete before Conv 5 — workflows depend on registered actions.

## Stories delivered

See `USER_STORIES.md` for full acceptance criteria.

- S1 — Electron CDP launcher (Conv 1)
- S2 — data-testid attributes (Conv 2)
- S3 — Pathly POMs (Conv 3)
- S4 — Pathly glue actions + site register (Conv 4)
- S5 — Smoke workflow end-to-end (Conv 5)
- S6 — Extension guide for future contributors (Conv 5)
