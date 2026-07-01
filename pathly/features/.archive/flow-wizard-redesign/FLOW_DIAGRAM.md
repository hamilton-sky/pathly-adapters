---
name: Flow Diagram
---
# flow-wizard-redesign - Flow Diagram

## Happy Path

```text
User opens wizard
  -> Step0Entry
     -> From template
        -> select template
        -> set states and transitions
        -> Step 1
     -> From name / Start blank
        -> blank template
        -> Step 1
  -> Step 1 Name your flow
  -> Step 2 Define stages
  -> Step 3 Assign agents
  -> Step 4 Quality & routing
  -> Step 5 Review & save
  -> Save Flow
```

## Draft and resume

```text
User saves draft
  -> draft JSON on disk
  -> reopen wizard
  -> Step0Entry shows Resume draft card
  -> user resumes
```
