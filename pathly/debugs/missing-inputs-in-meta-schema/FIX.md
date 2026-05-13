# Fix — missing-inputs-in-meta-schema

## Fix
Added the `inputs` property to `src/pathly_data/schemas/pathly-meta.schema.json`. It is defined as an object with `additionalProperties` describing each named input parameter (with `description`, `required`, and optional `type` sub-fields).

## Files changed
- `src/pathly_data/schemas/pathly-meta.schema.json` — added `inputs` property block before the `hooks` property

## Why this fixes it
Adding `inputs` to the schema's `properties` means it is now an explicitly allowed key, so YAML files containing `inputs` blocks no longer violate the `"additionalProperties": false` constraint.
