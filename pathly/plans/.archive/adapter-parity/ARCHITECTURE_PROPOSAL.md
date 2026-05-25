---
name: Architecture Proposal
---
# adapter-parity — Architecture Proposal

## Skill file schema contract

All skill YAML files follow this structure:
```yaml
skill: <skill-name>            # required — matches the skill invocation name
filename: <SKILL_FILE.md>      # required — the core skill body file
natural_language: <phrase>     # required — how to invoke via chat
# Optional fields:
host: <claude|copilot|codex>   # if present, must match the adapter
variables:                     # optional substitution map
  KEY: value
```

**Rule:** When copying from Claude to Copilot/Codex, copy all fields verbatim. Only adjust `host:` if it exists. Do not add fields not present in the source.

## Explorer agent contract

The explorer agent sits between scout (structural questions) and builder (edits). It is read-only on source code but writes output files:

```
scout       → answers "where is X defined"    → returns findings
explorer    → traces "how does X work"         → writes TRACE.md / CONCLUSIONS.md
builder     → edits code                       → modifies source
```

Explorer's output files (`TRACE.md`, `CONCLUSIONS.md`) live in `pathly/plans/<feature>/` — same convention as other plan artifacts.

## CSS token cascade (focus rings)

```
tokens.css
  :root { --focus-ring: 2px solid #38BDF8; }      ← dark theme default
  [data-theme="paper"] { --focus-ring: 2px solid #c75c2a; }  ← per-theme

component.module.css
  .element:focus-visible { outline: var(--focus-ring); }   ← correct
  .element:focus-visible { outline: 2px solid #89b4fa; }   ← WRONG (hardcoded)
```

**Rule:** All `:focus-visible` rules must use `var(--focus-ring)`. No component CSS file should contain literal hex colors for focus states.
