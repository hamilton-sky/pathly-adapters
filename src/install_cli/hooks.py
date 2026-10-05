"""Merge Pathly's hook commands into a host's ``settings.json``.

Hook entries whose command contains ``pathly_hooks`` are Pathly-owned. ``settings.json`` is
the user's file, so everything else in it — other hooks, other settings — is preserved,
and a repair replaces Pathly's entries *in place* rather than moving them to the end.

Commands in ``install.yaml`` may contain ``{python}``, expanded to the interpreter that is
running the installer. That interpreter necessarily has the Pathly package (it just
imported ``install_cli``) and, being an absolute path, needs no ``python`` on ``PATH`` —
a bare ``python -m pathly_hooks…`` fails at every session end on a machine with only
``python3``, or one where the package lives in a venv or pipx environment.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

# Substring that identifies a hook command as Pathly-owned.
_PATHLY_HOOK_MARKER = "pathly_hooks"


def _quote_for_shell(path: str) -> str:
    if os.name == "nt":
        return f'"{path}"' if re.search(r"\s", path) else path
    return shlex.quote(path)


def expand_command(command: str) -> str:
    """Substitute ``{python}`` with this interpreter's absolute path, shell-quoted."""
    if "{python}" not in command:
        return command
    return command.replace("{python}", _quote_for_shell(sys.executable or "python3"))


def _is_pathly(hook: object) -> bool:
    return isinstance(hook, dict) and _PATHLY_HOOK_MARKER in hook.get("command", "")


def _has_pathly(group: object) -> bool:
    return isinstance(group, dict) and any(
        _is_pathly(h) for h in group.get("hooks", [])
    )


def _replace_in_place(groups: list, canonical: dict) -> list:
    """``groups`` with every Pathly hook entry replaced by ``canonical`` at the position of
    the first one. Other groups and other hooks inside a mixed group keep their order, and a
    group's own keys (e.g. ``matcher``) survive."""
    result: list = []
    placed = False
    for group in groups:
        if not _has_pathly(group):
            result.append(group)
            continue
        if not placed:
            result.append(canonical)
            placed = True
        others = [h for h in group.get("hooks", []) if not _is_pathly(h)]
        if others:
            result.append({**group, "hooks": others})
    return result


def _apply_hooks(host: str, hooks_cfg: dict, *, dry_run: bool, repair: bool) -> None:
    """Merge Pathly hooks into the host's settings.json.

    Normal mode adds a missing Pathly hook and leaves an existing one as-is; ``repair=True``
    brings existing Pathly hooks to the canonical commands in place. A repair that changes
    nothing writes nothing.
    """
    settings_dest_str = hooks_cfg.get("settings_dest")
    if not settings_dest_str:
        return
    settings_path = Path(settings_dest_str).expanduser()

    # event → [cmd, ...] (skip the settings_dest metadata key)
    events: dict[str, list[str]] = {
        k: [expand_command(c) for c in ([v] if isinstance(v, str) else list(v))]
        for k, v in hooks_cfg.items()
        if k != "settings_dest"
    }
    if not events:
        return

    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}

    existing_hooks: dict = settings.get("hooks", {})
    changed = False

    for event, commands in events.items():
        event_groups: list = list(existing_hooks.get(event, []))
        canonical = {"hooks": [{"type": "command", "command": cmd} for cmd in commands]}

        if not any(_has_pathly(g) for g in event_groups):
            new_groups = [*event_groups, canonical]
        elif repair:
            new_groups = _replace_in_place(event_groups, canonical)
        else:
            continue  # existing Pathly hooks, repair not requested — leave as-is

        if new_groups != event_groups:
            existing_hooks[event] = new_groups
            changed = True

    if not changed:
        return

    settings["hooks"] = existing_hooks

    if dry_run:
        print(f"[{host}] Would update hooks in {settings_path}")
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[{host}] Updated hooks in {settings_path}")
