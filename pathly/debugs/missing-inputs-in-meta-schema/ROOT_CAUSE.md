# Root Cause — missing-inputs-in-meta-schema

## Root Cause
The `inputs` property was added to agent meta YAML files (`orchestrator.yaml`) to declare agent input parameters, but was never added to `pathly-meta.schema.json`. Because the schema enforces `"additionalProperties": false`, any validator running the schema against those YAML files would reject them with a "Additional properties are not allowed" error.

## Affected Code
- `src/pathly_data/schemas/pathly-meta.schema.json` — missing `inputs` property definition; `additionalProperties: false` makes the omission a hard rejection

## Impact
- Both `claude` and `codex` orchestrator meta files fail schema validation
- Any future agent meta YAML that declares inputs would also fail until the schema is updated
