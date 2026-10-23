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

``root_spelling`` and ``lies_under`` say when two strings name the same folder, the way the host
that opens them does (the chief gate compares a request's root and files with the chief's own by
them). On Windows ``\\`` and ``/`` both separate; on any other host a backslash is an ordinary
file-name character, so a string that has one is not a spelling of any root, and the routes, which
open the raw string, would open a different folder than the slash form of it.

Pure functions, no imports from the rest of the package.
"""

from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path

_DRIVE_ROOT = re.compile(r"^[A-Za-z]:/")
_BARE_DRIVE = re.compile(r"^[A-Za-z]:$")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_BREAKERS = "/\\:\0"


def host_is_windows() -> bool:
    """True when this host reads ``\\`` as a path separator. The one switch the readings below
    take (a test patches it to try the other host).
    """
    return os.name == "nt"


def _on_this_host(text: str) -> str | None:
    """``text`` as this host's file system reads it with ``\\`` and ``/`` made one separator, or
    None when it is not a path there: empty, a NUL, or (not on Windows) a backslash, which names
    a file whose name has a backslash in it, not a folder the slash form of it names.
    """
    if not text or "\0" in text:
        return None
    if host_is_windows():
        return text.replace("\\", "/")
    return None if "\\" in text else text


def host_path(path: str) -> str | None:
    """``path`` as this host's file system reads it (``\\`` is a separator on Windows only), or
    None when it is not a path there: empty, a NUL, or, off Windows, a backslash.
    """
    return _on_this_host(path)


def root_spelling(value: object) -> str | None:
    """The one spelling of a project root, or None when ``value`` is not one: trailing slashes
    dropped (``/p/``, ``/p//`` are ``/p``, and ``/`` stays ``/``), nothing else changed (no ``.``
    or ``..`` collapse, no trimming, a drive letter's case kept). Two strings with one spelling
    are one folder when the routes open them as they are; a string with another spelling is not
    taken for the same root, though it may be.
    """
    if not isinstance(value, str):
        return None
    text = _on_this_host(value)
    return None if text is None else text.rstrip("/") or "/"


def normalise_root(value: str) -> str:
    """The key a project root is stored and looked up under: backslashes become ``/`` and
    trailing ``/`` are dropped (``/p/``, ``C:\\Users\\me\\proj\\`` are ``/p`` and
    ``C:/Users/me/proj``). A root that is only a separator or a drive keeps one ``/`` (``/``,
    ``C:\\`` are ``/`` and ``C:/``), because ``C:`` names the current folder of drive C and not
    its root. The empty string stays empty. Nothing else is changed: no ``.`` or ``..`` collapse,
    no trimming, no case change. Unlike ``root_spelling`` it does not ask whether the host reads
    the string as a path, so it is the same on every host.
    """
    text = value.replace("\\", "/")
    stripped = text.rstrip("/")
    if stripped == text:
        return text
    return stripped + "/" if not stripped or _BARE_DRIVE.match(stripped) else stripped


def cache_root(project_root: str) -> str:
    """The project part of a cache key: ``root_spelling`` of the root (so ``/p`` and ``/p/`` share
    their entries), else the string as given (a spelling this host does not read as a root names
    a folder of its own, so it keeps a key of its own). Two projects never share a key.
    """
    spelled = root_spelling(project_root)
    return project_root if spelled is None else spelled


def lies_under(path: object, root: str | None, anchored: bool) -> bool:
    """True when ``path`` lies under ``root`` (a ``root_spelling``) once its ``..`` segments are
    collapsed. A relative path is read against ``root`` when ``anchored`` (a route that joins it
    to the project, as ``/code/query`` does with its ``target``), else it is not a path of the
    project at all. A text check: symlinks are not followed, and a drive letter is compared as
    written. A string with a drive prefix (``C:``, and so ``a:b``) is an absolute path on every
    host, so it is refused unless it is under ``root``, though a POSIX host would read it as a
    relative name: the gate does not guess which of the two a route means.
    """
    text = _on_this_host(path) if isinstance(path, str) else None
    if text is None or not root:
        return False
    if not (text.startswith("/") or _DRIVE_PREFIX.match(text)):
        if not anchored:
            return False
        text = f"{root.rstrip('/')}/{text}"
    text = posixpath.normpath(text)
    base = root.rstrip("/")
    return text in (root, base) or text.startswith(base + "/")


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
