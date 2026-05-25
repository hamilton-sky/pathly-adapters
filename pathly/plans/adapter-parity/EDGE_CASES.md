---
name: Edge Cases
---
# adapter-parity — Edge Cases

## Skill parity

| Case | Expected behavior |
|---|---|
| `check_core.py` lint runs after new skills added | New YAML files pass lint; tool does not skip them due to path patterns |
| Codex adapter already has a `commit_skill.yaml` | Builder reads it first; if so, update rather than overwrite |
| `archive_skill.yaml` references a core skill file that doesn't exist | Build/install will fail; verify `filename:` points to an existing `.md` |

## Explorer agent

| Case | Expected behavior |
|---|---|
| `explorer.yaml` description differs from `explorer.md` description | They must match; builder should use the YAML description as authoritative |
| Future adapter (Cursor) added without explorer.yaml | That adapter's _meta/ simply lacks explorer.yaml — not an error |

## Copilot hooks removal

| Case | Expected behavior |
|---|---|
| `install.yaml` has other keys besides `hooks:` | Only `hooks:` removed; all others preserved exactly |
| Tests reference the `hooks:` key for copilot | Tests must be updated too (unlikely but check) |
| `install.yaml` has no `hooks:` key (already removed) | No-op — builder confirms file is clean and moves on |

## Focus ring token replacement

| Case | Expected behavior |
|---|---|
| `#89b4fa` appears in a comment | Replace if in a `:focus-visible` rule; leave if it's a code comment explaining the old color |
| `.dropTarget` background uses rgba with hardcoded color | Replace with `var(--accent-bg)` |
| A theme's `--focus-ring` value is not visible on that theme's background | This is a separate issue with the token definition, not this fix — flag but don't change tokens.css |
| `filterInput:focus` border-color rule (using `var(--accent)`) | Keep this rule — it's correct; only ADD the `:focus-visible` outline rule |
