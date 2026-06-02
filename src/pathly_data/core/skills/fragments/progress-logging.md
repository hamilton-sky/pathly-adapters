## Live progress logging

When this skill says `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>`,
run the corresponding command below, filling in the actual feature name, agent role, and phase:

```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE
```

- `<feature>` — the feature slug (folder name under `pathly/plans/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

If `pathly-fsm-call` is unavailable or the server is not running, skip silently.
Phase logging must never block the main workflow.
