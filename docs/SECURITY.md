# Pathly Adapters Security and Reliability Review

This document records the security/reliability posture for pathly-adapters and
the remaining hardening work before a production-ready label.

Current status: public beta candidate (core install path stable at 1.0.0).

The adapter architecture has good safety properties: thin adapters, an explicit
stitch pipeline, dry-run support, a Pathly-owned-file manifest, and atomic
installs with rollback. The main gaps are hook injection risks, file-write
scope enforcement, and marketplace manifest integrity checks.

---

## Hook Injection Risks

Hooks are installed by pathly-adapters into host tool settings. They run local
Python scripts after tool calls and can rewrite files.

Risk:

- Hook input comes from JSON on stdin and includes file paths.
- `classify_feedback.py` may call the Anthropic API when `ANTHROPIC_API_KEY` is
  present.
- Hook failures could silently leave feedback unclassified or without TTL
  metadata.
- A hook that validates paths incorrectly could write outside the intended
  project `plans/` directory.

Mitigation today:

- Hooks are narrow: they only act on feedback-file names or
  `feedback/IMPL_QUESTIONS.md`.
- `classify_feedback.py` exits silently if no API key exists or if questions
  are already tagged.
- `inject_feedback_ttl.py` only acts on known feedback filenames under a
  `feedback/` path segment.
- Setup scripts only touch host tool settings to register/unregister hooks.

Remaining gap:

- File path validation is string-based. A production hardening pass should
  resolve paths and ensure writes stay under the active project's `plans/`
  directory.
- Hook API failures are intentionally non-blocking, but not strongly
  observable.
- The model name in `classify_feedback.py` is a compatibility dependency and
  should be checked during release.

Production recommendation:

- Add path canonicalization before every hook write.
- Add hook unit tests for ignored paths, malformed JSON, already-tagged files,
  missing API key, existing `DESIGN_QUESTIONS.md`, and TTL frontmatter.
- Log hook failures in a project-local diagnostic file or clearly visible hook
  output.
- Document that hooks are optional and the pipeline must remain correct
  without them.

Allowed hook behavior:

- Validate paths.
- Add TTL metadata to known feedback files.
- Classify `IMPL_QUESTIONS.md` into `[REQ]` / `[ARCH]` tags.
- Emit diagnostics for stale state or malformed payloads.
- Run fast FSM consistency checks.

Prohibited hook behavior:

- Long-running workflows.
- Lifecycle agent spawning.
- Source edits.
- Hidden state advancement.
- Unsupported host schemas presented as working.

Hook failures must be visible and recoverable. They must not corrupt workflow
state.

---

## Subprocess Calls in Installer

Files reviewed:

- `install_cli/detect.py`
- `install_cli/materialize.py`
- `install_cli/setup_command.py`

Risk:

- `detect.py` may invoke shell commands to locate host tool config directories.
- `materialize.py` writes files to user-level config directories.

Mitigation today:

- Subprocess calls in installer use argument lists rather than shell string
  interpolation.
- `--dry-run` mode never writes any files.

Production recommendation:

- Subprocess calls in installer should set timeouts.
- Installer subprocess failures should produce clear diagnostics, not silent
  fallback.

---

## File Write Safety

Risk:

- Installer writes to `~/.claude/`, `~/.codex/`, and Copilot workspace paths.
- `--force` could overwrite user-owned files not created by Pathly.
- A stale manifest could misidentify non-Pathly files as Pathly-owned.

Mitigation today:

- A Pathly-owned-file manifest tracks what `materialize.py` wrote.
- `--repair` only overwrites files listed in the manifest.
- `--force` is an explicit opt-in that overwrites everything.
- Install is atomic — if anything fails, already-written files are rolled back.
- `--uninstall` only removes files tracked in the manifest.

Remaining gap:

- Manifest integrity is not verified on load (could be edited externally).
- Rollback completeness needs an end-to-end test for partial-failure scenarios.

Production recommendation:

- Add tests for partial install failure and rollback correctness.
- Document explicitly which files are Pathly-owned vs. user-owned.
- `--uninstall` should confirm the manifest is intact before deleting files.

---

## Trust Boundaries (Adapter Side)

The adapter layer operates before any AI tool processes Pathly's files. Its
trust responsibilities:

- `core/` content is trusted workflow behavior. It is never modified by the
  installer.
- `adapters/<tool>/_meta/*.yaml` files are trusted adapter metadata, also
  never modified by the installer.
- Files written to `~/.claude/`, `~/.codex/`, etc. are Pathly-generated and
  must not contain user-provided free text that could inject instructions into
  a host tool context.
- The stitch pipeline combines fixed core content with fixed adapter metadata.
  It does not interpolate user input into the stitched output.

Production hardening still needed:

- Confirm stitch output is deterministic and contains no user-controlled
  content.
- Adapter-specific checks that prevent host-only instructions from leaking
  into core prompts during a future stitch implementation change.

---

## Marketplace Manifest Integrity

Risk:

- `adapters/claude/.claude-plugin/plugin.json`, `adapters/codex/.codex-plugin/plugin.json`,
  and `.agents/plugins/marketplace.json` are trusted by Claude Code and Codex.
- A malformed or tampered manifest could cause the host tool to load the wrong
  files or fail silently.

Mitigation today:

- Manifests are committed to version control.
- CI validates manifests parse as JSON.

Production recommendation:

- Add schema validation for manifests in CI, not just JSON parse checks.
- Pin manifest schema versions where host tools support versioning.
- Document what each manifest field controls and what is safe to change.

---

## Production Readiness Checklist

Required before production-ready:

- Hook unit tests for path validation and failure modes.
- Partial install / rollback test.
- Plugin manifests parse as valid JSON (CI-enforced).
- No install command writes files during `--dry-run`.
- `--uninstall` leaves no Pathly residue.
- Stitch pipeline output contains no user-controlled content.

Recommended before public beta:

- Schema validation for plugin manifests in CI.
- Hook path canonicalization.
- Manual smoke-test guide for Claude Code install, Codex install, and Copilot
  install.
