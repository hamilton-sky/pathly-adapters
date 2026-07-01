# AI-Assisted Flow Wizard - Flow Diagram

## Draft and save path

```text
Sidebar -> Open Flow Wizard
            |
            v
      AiDraftPanel (optional)
       intent + Generate Draft
            |
            v
       llmBridge.ts
            |
            v
    candidate full FlowYaml
            |
            v
 shared parse + validate boundary
       |                 |
       | invalid         | valid
       v                 v
 show issues;       apply draft to
 preserve state     wizard fields
                         |
                         v
              user edits/reviews schema
                         |
                         v
               canonical YAML preview
                         |
                         v
                    validated save
                         |
                         v
                FlowEditor reads YAML
```

## Responsibility boundary

```text
AI assistance:        propose typed flow data
Wizard:               edit and approve flow data
Validator/serializer: enforce runtime-compatible document
Runtime:              execute saved Pathly flow later
External UI healing:  separate future execution feature
```
