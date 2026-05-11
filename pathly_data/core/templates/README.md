# Core Templates

Tool-agnostic plan, debug, feedback, and retro templates belong here.

`core/templates/` is the canonical template source. Adapter and runtime install
surfaces copy these files into host-specific locations, but workflow prompts
should refer back to these core templates first.

Current template sets:

- `plan/`: Pathly plan files used by planning and import workflows.

Repo-root `templates/` is intentionally absent; do not add a duplicate install
surface there.
