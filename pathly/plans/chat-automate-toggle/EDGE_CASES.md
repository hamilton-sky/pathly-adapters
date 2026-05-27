# AI-Assisted Flow Wizard - Edge Cases

## Schema integrity

| Case | Required behavior |
|---|---|
| A loaded flow contains `role_map`, `transition_actions`, or `gates`. | Wizard preserves and exposes those fields on save. |
| A transition references an unknown state. | Show validation error and disable Save. |
| A transition rule or transition action targets an undeclared edge. | Show edge-specific validation error and disable Save. |
| Feedback routing names a role not present in `role_map` or permitted mapping. | Show a validation error or an explicit warning according to runtime rules. |
| Duplicate or empty state names are entered. | Reject before serialization. |
| User enters text in a description/intention field. | Never silently imply it is saved to runtime YAML; keep it explicitly draft-only or remove it. |

## AI drafting

| Case | Required behavior |
|---|---|
| Model returns malformed JSON/YAML or markdown-wrapped output. | Parse defensively; show generation error; retain existing editable data. |
| Model returns a structurally valid but semantically invalid flow. | Populate only after schema validation policy is met, or show draft issues without enabling Save. |
| User already edited fields before requesting a new draft. | Do not overwrite silently; require deliberate apply/replace action. |
| User aborts generation or the bridge errors. | Stop loading state and keep current wizard draft unchanged. |
| Model generates unsupported fields. | Reject or ignore only with explicit feedback; never write hidden behavior accidentally. |

## Runtime and verification

| Case | Required behavior |
|---|---|
| Existing Ollama bridge type error remains. | Treat as prerequisite work; do not claim a zero-error acceptance baseline until fixed. |
| An existing flow is opened without AI. | Editing and saving work normally; AI is optional. |
| A later feature executes a flow against an external webpage and locators drift. | Handle through a separate resolver/healing execution capability, not this wizard plan. |
