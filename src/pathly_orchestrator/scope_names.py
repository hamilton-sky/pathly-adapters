"""What a board scope or a slug may look like before the server turns it into a path.

A board scope arrives in a request body and is stored with the row it was posted with. Two
places later make a path of it: the board mirror (``board_mirror``) writes
``<project root>/pathly/project/BOARD.json`` for a project board and
``<project root>/pathly/features/<scope>/BOARD.json`` for a feature board, and the goal run and
decompose make ``pathly/features/<f>/goals/<slug>``. The chief gate (``http_server/chief_project``)
refuses what these predicates refuse, so a gate and a sink cannot disagree about a spelling.

``flow`` and ``skill`` are request strings too: ``fsm_ops._load_flow`` reads the packaged
``core/flows/<flow>.flow.yaml`` and ``skills/compose_resources`` reads ``core/skills/<skill>.md``,
and a goal run makes ``pathly/features/<scope>/<flow>/<slug>`` of its flow. ``is_flow_name`` and
``is_skill_name`` say what may join onto those folders; the gate and the readers both ask them.

Pure functions, no imports from the rest of the package.
"""

from __future__ import annotations

import re
from pathlib import Path

_DRIVE_ROOT = re.compile(r"^[A-Za-z]:/")
_BREAKERS = "/\\:\0"


def is_segment(value: object) -> bool:
    """True for one plain folder name: a non-blank string with no ``/``, ``\\``, drive colon or
    NUL, that is not made of dots only (``.``, ``..``). Spaces, dots inside a name and non-ASCII
    letters are fine (``Q3 plan``, ``v1.2.3``, ``café``).
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text) and set(text) != {"."} and not any(c in text for c in _BREAKERS)


def is_project_root(value: object) -> bool:
    """True for a normalised absolute project root, the scope of a project board: forward
    slashes only, no trailing slash, no ``.`` or ``..`` segment, and absolute, either POSIX
    (``/home/me/proj``, ``//server/share/proj``) or with a drive letter (``C:/Users/me/proj``).
    """
    if not isinstance(value, str) or not value.strip("/"):
        return False
    if "\\" in value or "\0" in value or value.endswith("/"):
        return False
    if not (value.startswith("/") or _DRIVE_ROOT.match(value)):
        return False
    return not any(part in (".", "..") for part in value.split("/"))


def is_flow_name(value: object) -> bool:
    """True for a flow's name: one folder name (``is_segment``), the way a flow is stored
    (``core/flows/<name>.flow.yaml``, a database row's name, the folder a run is made in).
    """
    return is_segment(value)


def is_skill_name(value: object) -> bool:
    """True for a skill's name, ``name`` or ``category/name``: forward-slash separated parts that
    are each one folder name. No absolute path, no ``..``, no backslash, drive colon or NUL.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    return all(is_segment(part) for part in value.split("/"))


def resolves_inside(root: object, candidate: object) -> bool:
    """True when ``candidate`` resolves (symlinks followed) to a path under ``root``.

    For two real paths only; a packaged resource that is not a file on disk (a zipped wheel) has
    no symlinks to follow and is answered True, since its name was checked by the predicates
    above.
    """
    if not (isinstance(root, Path) and isinstance(candidate, Path)):
        return True
    return candidate.resolve().is_relative_to(root.resolve())
