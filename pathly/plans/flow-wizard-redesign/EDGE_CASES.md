---
name: Edge Cases
---
# flow-wizard-redesign - Edge Cases

## Template selection

- Switching templates overwrites states and transitions with the new template defaults.
- Selecting Start blank resets the template-owned arrays to empty values.

## Step consolidation

- Collapsed accordion sections still preserve any entered quality data.
- Saving with all accordion sections collapsed still produces valid YAML.

## Validation

- One-state flows remain valid and should not trigger the non-terminal agent warning.
- Missing non-terminal agent assignments warn but do not block advancing.

## Drafts

- A corrupted draft file is ignored silently.
- Resume draft uses defaults for missing fields.
- Starting over deletes any saved draft on disk.

## Step 2 drag behavior

- Dragging a single state has no effect.
- Reordering updates the pipeline chain immediately.
- HTML5 drag is the only supported drag mechanism in this plan.
