# orchestrator-skill-delegation — Flow Diagram

## Before: Orchestrator implements inline

```
Orchestrator (FSM loop)
        │
        │  transition fires
        ▼
Execute transition_actions  ←── 30 lines of inline logic
        │
        ├─ type: git_commit ──► git add -A && git commit  (shell command in orchestrator)
        ├─ type: update_progress ──► edit PROGRESS.md     (file edit in orchestrator)
        └─ type: archive_artifacts ──► copy files         (file copy in orchestrator)
        │
        ▼
Continue FSM loop
```

## After: Orchestrator delegates to skills

```
Orchestrator (FSM loop)
        │
        │  transition fires
        ▼
Execute transition_actions  ←── 10 lines, pure delegation
        │
        │  read action.skill
        ▼
Spawn skill by name ──────────────────────────────────────────┐
        │                                                     │
        ├─ skill: commit ──────────────────► commit skill     │
        │                                    - check feedback │
        │                                    - git add -A     │
        │                                    - git commit     │
        │                                    - ACTION_DONE    │
        │                                    - return ────────┤
        │                                                     │
        └─ skill: archive-artifacts ──► archive-artifacts     │
                                        - read feedback/      │
                                        - copy to artifacts/  │
                                        - ACTION_DONE         │
                                        - return ─────────────┘
        │
        ▼
Continue FSM loop
```

## Feedback guard (moved into commit skill)

```
commit skill invoked
        │
        ▼
Check <storage_path>/feedback/ for *.md
        │
        ├─ file found ──► "commit suppressed — active feedback: <name>"
        │                  exit cleanly (no commit)
        │
        └─ no files ──► git add -A
                         git commit -m <message>
                         append ACTION_DONE
                         return
```

## Component Legend

| Symbol | Meaning |
|---|---|
| Orchestrator | FSM router — spawns agents and skills, never implements |
| Execute transition_actions | 10-line dispatch loop — reads `skill:` key, spawns, waits |
| commit skill | Stages + commits with feedback-file guard |
| archive-artifacts skill | Copies feedback files to pipeline-walkthrough/artifacts/ |
| ACTION_DONE | Event appended to EVENTS.jsonl by each skill on completion |
