# Claude Code Adapter

> **Note:** the `/pathly` slash-commands + `pathly-setup` install path described here are
> Pathly's **interactive (secondary)** mode. The **primary** runtime is headless — Studio's
> runner injects the full composed prompt into Claude via argv at spawn time (no installed skill
> file is read). See the repo `README.md` / `docs/WHAT_IS_PATHLY.md`.

Claude Code should expose the cross-framework Pathly entry points:

```text
/pathly ...
/path ...
```

`/pathly` is canonical. `/path` is the short alias for daily use.

Claude Code can keep the existing command names for backwards compatibility:

```text
/go
/help
/debug
/explore
/team-flow
```

When docs or generated help describe the portable Pathly command surface, prefer
`/pathly` examples and mention that `/path` is equivalent.

Skills are loaded directly from `core/skills/` — no adapter wrappers needed.
`adapters/claude/agents/` provides Claude Code-specific agent files with
`tools:[]` frontmatter and `Agent()` invocation syntax for subagent spawning.

## Install

```bash
pip install -e pathly-adapters/
pathly-setup claude --apply
```

Preview writes first:

```bash
pathly-setup claude --dry-run
```

Current status: `pathly-adapters/core/skills/` and `pathly-adapters/adapters/claude/agents/` provide the working Claude Code install path via `pathly-setup`.
