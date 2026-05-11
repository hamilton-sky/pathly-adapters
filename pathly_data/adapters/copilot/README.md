# Copilot Adapter

Installs Pathly agent files into VS Code with GitHub Copilot.

## Install

```bash
pip install -e pathly-adapters/
pathly-setup copilot --apply
```

Preview writes first:

```bash
pathly-setup copilot --dry-run
```

## Status

Public beta. Copilot agent file destinations follow the VS Code Copilot agent spec. Verify the destination path matches your VS Code version before using `--apply`.

## Notes

- Copilot does not expose slash commands in the same way as Claude Code. Agent files are loaded as custom instructions; invocation syntax depends on the Copilot version.
- Keep Claude Code slash-command examples (e.g. `/pathly help`) separate from Copilot usage — they are different surfaces.
- Do not mix adapter agent files between hosts: each adapter's `_meta/*.yaml` is tuned for that host's model frontmatter and tool syntax.
