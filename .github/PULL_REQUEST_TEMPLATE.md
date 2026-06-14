## What this PR does

<!-- One paragraph: what changed and why. -->

## Checklist

- [ ] `CHANGELOG.md` has an entry for this change (required for any user-visible change)
- [ ] Version bumped in `pyproject.toml` if this is a release (and `package.json` + `studio/package.json` match)
- [ ] `python scripts/check_version_sync.py` passes locally
- [ ] `python scripts/check_adapters.py` passes (required if adding/removing an adapter)
- [ ] `python scripts/check_entry_points.py` passes (required if changing `pyproject.toml` scripts)
- [ ] `pytest` passes
- [ ] Docs updated if the change affects adapters, entry points, skills, or agents

## Adapter changes (if any)

If you added or removed an adapter, confirm all four places are updated:

- [ ] `src/pathly_data/adapters/<name>/` directory created/removed
- [ ] `install_cli/orchestrate.py` — `ALLOWED_HOSTS`
- [ ] `install_cli/detect.py` — `_HOST_MARKERS`
- [ ] `pathly_orchestrator/fsm/state.py` — `_KNOWN_ADAPTERS`
