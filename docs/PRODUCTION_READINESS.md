# Pathly Adapters Production Readiness

Release criteria for pathly-adapters. Until these gates are met, describe
pathly-adapters publicly as a public beta / technical preview.

## Release Position

pathly-adapters is currently:

- Stable (1.0.0) for the core install path (`--dry-run`, `--apply`, `--uninstall`).
- Verified with full rollback on failure.
- Supported for Claude Code through the existing install scripts.
- Ready for Codex plugin testing through `adapters/codex/.codex-plugin/plugin.json`.
- Copilot destination paths follow the VS Code Copilot agent spec and may
  require `--repair` after a VS Code update.
- Not yet fully adapter-based for Cursor, Windsurf, BMAD, or generic prompts.

## Claude Code Install Checks

Required before calling the release production-ready:

- Install scripts work on macOS, Linux, and Windows.
- `adapters/claude/.claude-plugin/plugin.json` parses as valid JSON.
- Plugin manifest validates against the Claude Code plugin schema.
- Smoke tests confirm every documented skill exists under `~/.claude/skills/`
  after install.
- Smoke tests confirm every README command maps to a real installed skill.
- Clean-machine smoke run for Claude Code install and uninstall.
- `--repair` correctly re-installs Pathly-owned files that were modified or
  deleted.

## Codex Readiness

Done:

- `adapters/codex/.codex-plugin/plugin.json` committed.
- Public Codex marketplace metadata at `.agents/plugins/marketplace.json`.
- `pathly-setup codex --apply` creates the Codex local marketplace files.

Still needed:

- Test local plugin install in a clean Codex environment.
- Confirm how Codex displays the skill prompts in the current app build.
- Add Codex-specific install screenshots or exact UI steps once verified.
- Keep docs clear that Codex uses natural-language skill prompts, not
  `/pathly` slash commands in current builds.
- Clean-machine smoke run for Codex local marketplace install.

## Copilot Readiness

- Copilot destination paths follow the VS Code Copilot agent spec.
- `pathly-setup copilot --apply` installs agent files as Copilot custom
  instructions.
- May require `--repair` after a VS Code update changes the agent spec path.
- Invocation syntax varies by VS Code / Copilot version — document verified
  steps after testing.

## pathly-setup Flags

Required before production-ready:

- `--dry-run` never writes any files.
- Dry-run output shows: detected hosts, Pathly version, planned adapter writes,
  existing files that would be replaced, final start command per host.
- `--apply` is the only flag that mutates host config.
- `--repair` overwrites only Pathly-owned files (tracked in manifest).
- `--force` overwrites all files, including non-Pathly-owned.
- `--uninstall` removes all Pathly-owned files with no orphan residue.
- Unsupported or missing hosts produce useful next steps, not a crash.

## Package Build and Publish

Required before production-ready:

- `python -m build` produces a wheel with all `pathly_data/` assets included.
- `pip install dist/pathly-adapters-*.whl` in a fresh venv:
  - `pathly-setup --version` works.
  - `pathly-setup doctor` works.
  - All `pathly_data/` resources are readable from installed wheel.
  - No command depends on the source checkout path.
- `twine upload dist/*` succeeds for PyPI release.
- PyPI package name `pathly-adapters` reserved.

## Marketplace Manifests

Required before production-ready:

- `adapters/claude/.claude-plugin/plugin.json` parses as valid JSON.
- `adapters/codex/.codex-plugin/plugin.json` parses as valid JSON.
- `.agents/plugins/marketplace.json` parses as valid JSON.
- All three manifests are validated in CI.

## Naming

Public brand: `Pathly`
Python distribution: `pathly-adapters`
CLI command: `pathly-setup`

Before publishing broadly:

- Check PyPI package name `pathly-adapters` availability.
- Keep uninstall cleanup scoped to Pathly-owned files only.

## Multi-Tool Adapters

Use `docs/INSTALLER_DESIGN.md` as the long-term architecture, but do not block
the beta release on future adapters.

Adapter work should begin when there is real demand for:

- Cursor rules.
- Windsurf rules.
- BMAD chat modes.
- Generic copy-paste prompts.

## Quality Gates

Required before production-ready:

- `pytest -q` passes.
- GitHub Actions green on Python 3.11, 3.12, and 3.13.
- Plugin manifests parse as valid JSON.
- Install scripts pass dry-run or temp-home smoke tests.
- README start commands are covered by skill existence checks.
- Security and reliability notes are current.
- Public known-limitations section exists in README.

Recommended:

- Changelog for every public release.
- Version tag before large restructuring.
- Example walkthroughs:
  - Claude Code install + first `/pathly help`.
  - Codex local marketplace install + first `Use Pathly help`.

## Security Notes

Before broad distribution, make these explicit in README:

- Install scripts write to user-level AI tool config directories.
- Hook setup modifies Claude Code settings only when the user runs the hook
  setup script.
- No production source files are modified by install scripts.
- No network access is required after the repository is cloned.
- `--repair` and `--force` are explicit opt-in — default install never
  overwrites non-Pathly-owned files.
