"""``pathly-setup <host> --list`` and ``--remove <skill>``: CLI parity with the Studio picker.

The picker's model is declarative — the desired set is {defaults ∪ requested} and a
``--repair`` apply makes the host match it, pruning the rest. ``--remove`` is the same
reconcile scoped to the skills destination: the desired set is *installed − removals*,
so exactly the removed skills' files fall outside it and only those are pruned, through
the same ``materialize`` prune primitive (and the same prune reporting) the full apply
uses. Kept skills are not rewritten, and agents / flows / templates / hooks / MCP are not
touched — a full ``--apply --repair`` refreshes all of those, which a remove must not.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .materialize import materialize, owned_names
from .orchestrate import _load_install_yaml
from .report import report_pruned, report_would_prune
from .skill_catalog import (
    SkillInfo,
    dependents_of,
    installed_keys,
    load_catalog,
    resolve_skill_args,
)


def _skills_context(host: str) -> tuple[Path, dict[str, SkillInfo]] | None:
    skills_cfg = _load_install_yaml(host).get("skills")
    if not skills_cfg:
        print(f"[{host}] has no skills destination — nothing to do.", file=sys.stderr)
        return None
    dest = Path(skills_cfg["destination"]).expanduser()
    return dest, load_catalog(host, nested=skills_cfg.get("structure") == "nested")


def unknown_everywhere(hosts: list[str], names: set[str]) -> list[str]:
    """Names no targeted host defines — a typo, as opposed to a skill only some hosts have."""
    resolved_anywhere: set[str] = set()
    for host in hosts:
        ctx = _skills_context(host)
        if ctx is None:
            continue
        _, catalog = ctx
        _, unknown = resolve_skill_args(catalog, sorted(names))
        resolved_anywhere |= names - set(unknown)
    return sorted(names - resolved_anywhere) if names else []


def _state(info: SkillInfo, *, on_disk: bool, tracked: bool) -> str:
    if info.default:
        return "default" if on_disk else "default (not installed)"
    if not on_disk:
        return "available"
    return "installed" if tracked else "installed (untracked)"


def run_list(host: str) -> bool:
    """Print every skill the host defines with its state. Read-only."""
    ctx = _skills_context(host)
    if ctx is None:
        return False
    dest, catalog = ctx
    owned = owned_names(dest)
    installed = installed_keys(catalog, dest)

    rows = [
        (
            key,
            catalog[key].dirname or catalog[key].filename,
            _state(
                catalog[key],
                on_disk=key in installed,
                tracked=catalog[key].filename in owned,
            ),
            ", ".join(catalog[key].requires) or "-",
        )
        for key in sorted(catalog)
    ]
    n_default = sum(1 for k in installed if catalog[k].default)
    print(
        f"[{host}] {len(installed)} of {len(catalog)} skills installed in {dest} "
        f"({n_default} default):"
    )
    w_key = max(len("SKILL"), *(len(r[0]) for r in rows))
    w_dir = max(len("DIR"), *(len(r[1]) for r in rows))
    w_state = max(len("STATE"), *(len(r[2]) for r in rows))
    print(f"  {'SKILL':<{w_key}}  {'DIR':<{w_dir}}  {'STATE':<{w_state}}  REQUIRES")
    for key, dirname, state, requires in rows:
        print(f"  {key:<{w_key}}  {dirname:<{w_dir}}  {state:<{w_state}}  {requires}")
    print(
        f"\n  add:    pathly-setup {host} --export <skill>"
        "   (also installs what it requires; with --apply --repair the set is exact:"
        " anything not named is pruned)"
        f"\n  remove: pathly-setup {host} --remove <skill>"
        "   (refused while an installed skill requires it)"
    )
    return True


def run_remove(host: str, names: list[str], *, dry_run: bool = False) -> bool:
    """Remove the named non-default skills. All-or-nothing: any problem removes nothing."""
    ctx = _skills_context(host)
    if ctx is None:
        return False
    dest, catalog = ctx

    keys, unknown = resolve_skill_args(catalog, names)
    if unknown:
        print(
            f"[{host}] Error: unknown skill(s): {', '.join(unknown)} "
            f"(see `pathly-setup {host} --list`)",
            file=sys.stderr,
        )
        return False

    owned = owned_names(dest)
    installed = installed_keys(catalog, dest)
    problems: list[tuple[str, str]] = []
    to_remove: list[str] = []
    for key in keys:
        info = catalog[key]
        if info.default:
            problems.append(
                (
                    key,
                    "it is in the default tier and always installed "
                    "(`--uninstall` removes everything)",
                )
            )
        elif key not in installed:
            print(f"[{host}] {key!r} is not installed — nothing to remove.")
        elif not any(info.owns(n) for n in owned):
            problems.append(
                (
                    key,
                    "it is on disk but not tracked in the manifest, "
                    "so Pathly will not delete it",
                )
            )
        else:
            to_remove.append(key)

    # A skill another installed skill needs stays — unless that skill is going too.
    staying = installed - set(to_remove)
    for key in list(to_remove):
        needed_by = dependents_of(catalog, key, staying)
        if needed_by:
            to_remove.remove(key)
            problems.append(
                (
                    key,
                    f"it is required by installed skill(s): {', '.join(needed_by)} "
                    f"(remove those too, e.g. "
                    f"{' '.join(f'--remove {n}' for n in [*needed_by, key])})",
                )
            )

    if problems:
        for key, reason in problems:
            print(f"[{host}] Error: cannot remove {key!r}: {reason}", file=sys.stderr)
        return False
    if not to_remove:
        return True

    doomed = {n for n in owned if any(catalog[k].owns(n) for k in to_remove)}
    if dry_run:
        report_would_prune(
            host,
            "skill file(s)",
            dest,
            {},
            repair=True,
            prune_filter=doomed.__contains__,
            why="requested",
        )
        return True

    pruned: list[str] = []
    materialize(
        {},
        dest,
        repair=True,
        prune_filter=doomed.__contains__,
        pruned_out=pruned,
    )
    report_pruned(host, "skill file(s)", dest, pruned, why="requested")
    return True
