# Pathly Adapters System Review

Internal review of pathly-adapters' current shape and release posture.

## Current Strengths

- Host-neutral core: `core/` owns reusable agent contracts, skill logic, and
  templates; host packaging is entirely in `adapters/`. Adding a new host
  requires only new `_meta/` files — no changes to `core/`.
- Stitch pipeline: `stitch.py` deterministically combines fixed core content
  with fixed adapter metadata. The output is predictable and auditable.
- Atomic install: `materialize.py` tracks Pathly-owned files in a manifest and
  rolls back already-written files if anything fails.
- Dry run: `--dry-run` shows exactly what would be written before any mutation
  happens.
- Repair semantics: `--repair` overwrites only Pathly-owned files; `--force` is
  an explicit opt-in for everything else. User-owned files are not touched by
  default.
- Codex support has both a plugin adapter and public marketplace metadata.

## Current Risks

- pathly-adapters is at 2.11.9 for the core install path, but Copilot
  destination paths may require `--repair` after a VS Code update.
- Hook path validation is string-based. A hardening pass is needed to resolve
  paths and confirm writes stay inside `plans/`.
- Manifest integrity is not verified on load — an externally edited manifest
  could misidentify non-Pathly files as Pathly-owned, causing `--uninstall` to
  delete user files.
- End-to-end clean-machine smoke tests for Codex local marketplace install are
  not yet complete.
- Cursor, Windsurf, BMAD, and generic prompt adapters are planned but not yet
  shipped.

## Design Decisions To Preserve

- Keep `core/` content host-neutral — no host-specific slash-command or
  sub-agent API syntax.
- Keep adapters thin — `_meta/*.yaml` adds host syntax on top; it does not
  duplicate core logic.
- Keep the stitch pipeline deterministic — no user-controlled content in
  stitched output.
- Keep `--apply` required for any writes; `--dry-run` is the safe default.
- Keep the Pathly-owned-file manifest — `--uninstall` must not remove
  user-owned files.
- Keep hooks optional — the pipeline must remain correct without them.

## Current Implementation Map

```text
src/install_cli/detect.py        host discovery (Claude Code, Codex, Copilot)
src/install_cli/stitch.py        core/ + _meta/*.yaml → deployable agent/skill files
src/install_cli/materialize.py   atomic write to host config + manifest tracking
src/install_cli/setup_command.py pathly-setup CLI (dry-run, apply, repair, force,
                               uninstall, per-host subcommands)
src/pathly_data/core/agents/                 14 host-neutral agent behavior contracts
src/pathly_data/core/skills/                 39 skill files (29 user-facing + 2 transition-action
                                             + 7 team sub-skills + 1 internal utility)
src/pathly_data/core/flows/                  4 FSM flow definitions (team, debug, explore, test)
src/pathly_data/core/templates/plan/         plan file templates
src/pathly_data/adapters/claude/_meta/       per-agent/skill YAML for Claude Code
src/pathly_data/adapters/codex/_meta/        per-agent/skill YAML for Codex
src/pathly_data/adapters/copilot/_meta/      per-agent/skill YAML for Copilot
```

## Recommended Next Hardening

1. Add path canonicalization in hook writes — confirm all writes stay inside
   the active project's `plans/` directory.
2. Add manifest integrity verification on load to prevent stale or edited
   manifests from causing `--uninstall` to delete user-owned files.
3. Add a partial-install / rollback end-to-end test.
4. Run clean-machine smoke tests for Claude Code install and Codex local
   marketplace install.
5. Add schema validation for plugin manifests in CI (beyond just JSON parse).
6. Keep release docs at public beta for Codex and Copilot until smoke tests
   confirm correct behavior on clean machines.
