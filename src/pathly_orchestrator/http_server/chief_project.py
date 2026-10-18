"""Which project a chief's request names, and whether it is the session's (chief-agent).

``project_refusal`` applies ``chief_fields.ROUTE_FIELDS`` to one request: the fields its route
reads as a project root, a board scope or a file, read from the JSON body of a POST and from the
query string of a GET, the way the view reads them. A value is the chief's own when it is a
string that ``normalise_project_root`` maps to the session's root (forward slashes, no trailing
slash); anything else, a non-string included, is not. A file is the chief's own when it lies
under that root after its ``..`` segments are collapsed (text only: symlinks are not followed,
and a Windows drive letter is compared as written). A name the route joins into a path (a scope
marked ``segment``) is one folder name: no separator, no drive colon, not ``.`` or ``..``.

A route with no entry is refused, so a route added without one is not passed by default.
"""

from __future__ import annotations

import posixpath
import re
from typing import Mapping

from .chief_fields import ROUTE_FIELDS, Fields, ScopeRead, TextPath

ROOT_KEY = "project_root"
_BOARDS = ("feature", "project", "global")
_DRIVE = re.compile(r"^[A-Za-z]:")
_SEGMENT_BREAKERS = "/\\:\0"

NOT_OWN = "that is not this chief's project"
NOT_NAMED = "a chief names its project_root on this route"
NOT_INSIDE = "a chief names only files inside its project"
NOT_A_SEGMENT = "must be one folder name: no '/', '\\', ':' or '..'"
NO_ENTRY = "the gate has no project entry for this route"


def _normalise(value: str) -> str:
    from pathly_orchestrator.supervisor.chief_session import normalise_project_root

    return normalise_project_root(value)


def is_own(value: object, own: str) -> bool:
    """True when ``value`` names the project whose normalised root is ``own``."""
    return isinstance(value, str) and _normalise(value) == own


def _path_like(value: str) -> bool:
    return "/" in value or "\\" in value or bool(_DRIVE.match(value))


def _usable(value: object) -> bool:
    """A value a route takes as a scope: truthy, and not a blank string."""
    return bool(value) and not (isinstance(value, str) and not value.strip())


def _board(source: Mapping, read: ScopeRead) -> str | None:
    """The board a scope read applies to; None when it has no board (a bare scope id)."""
    if read.board_key is None:
        return read.board
    raw = source.get(read.board_key)
    name = raw.strip() if isinstance(raw, str) else ""
    return name if name in _BOARDS else (read.board or "feature")


def _first_usable(source: Mapping, read: ScopeRead) -> tuple[str, object] | None:
    """The key and value a route takes as the scope: the first of ``keys`` with a usable value."""
    for key in read.keys:
        if _usable(source.get(key)):
            return key, source.get(key)
    return None


def _not_a_segment(value: object) -> bool:
    """True when ``value`` cannot be one folder name (a non-string cannot, for the route)."""
    if not isinstance(value, str):
        return True
    text = value.strip()
    return text in (".", "..") or any(c in text for c in _SEGMENT_BREAKERS)


def _bound_scope(source: Mapping, read: ScopeRead) -> object:
    """The scope the route will use if it is one the chief's project must own, else None."""
    found = _first_usable(source, read)
    if found is None:
        return None
    value = found[1]
    if isinstance(value, str):
        text = value.strip()
        if text in read.skip_exact or text.startswith(read.skip_prefix):
            return None
    board = _board(source, read)
    if board is None:
        # A bare scope id is a project root when it looks like a path; else a feature name.
        return None if isinstance(value, str) and not _path_like(value) else value
    return value if board == "project" else None


def _under(path: str, own: str, anchored: bool) -> bool:
    """True when ``path`` lies under ``own``. A relative path is read against ``own`` when it is
    ``anchored`` (a code query's target), else it is not a path of the project at all.
    """
    text = path.strip().replace("\\", "/")
    if not own:
        return False
    if not (text.startswith("/") or _DRIVE.match(text)):
        if not anchored:
            return False
        text = f"{own.rstrip('/')}/{text}"
    text = posixpath.normpath(text)
    base = own.rstrip("/")
    return text in (own, base) or text.startswith(base + "/")


def _recovered_path(source: Mapping, read: TextPath) -> str | None:
    """The path a post of ``when_type`` takes from its prose when ``path_key`` is blank."""
    given = source.get(read.path_key)
    if (isinstance(given, str) and given.strip()) or source.get(
        "type"
    ) != read.when_type:
        return None
    text = source.get(read.text_key)
    if not isinstance(text, str):
        return None
    from .blueprints.comms._helpers import extract_artifact_path

    return extract_artifact_path(text)


def _foreign_root(fields: Fields, body: Mapping, args, own: str) -> bool:
    """A project root anywhere in the request that is not the chief's, whether the route reads
    it or not.
    """
    return any(
        value and not is_own(value, own)
        for key in {ROOT_KEY, *fields.roots}
        for value in (body.get(key), *args.getlist(key))
    )


def _unnamed_root(fields: Fields, source: Mapping, view_args: Mapping) -> bool:
    """The route falls back to another project unless the root is named where it reads it."""
    must_name = (
        fields.names_root
        or any(source.get(k) for k in fields.names_root_when)
        or view_args.get("action") in fields.names_root_verbs
        or (
            bool(fields.names_root_unless)
            and not any(_usable(source.get(k)) for k in fields.names_root_unless)
        )
    )
    return must_name and not any(source.get(k) for k in fields.roots)


def _foreign_file(fields: Fields, source: Mapping, own: str) -> bool:
    """A file the route reads or stores that lies outside the chief's project."""
    for keys, anchored in ((fields.paths, True), (fields.abs_paths, False)):
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                if not _under(value, own, anchored):
                    return True
    for text_read in fields.text_paths:
        value = _recovered_path(source, text_read)
        if value is not None and not _under(value, own, False):
            return True
    return False


def project_refusal(
    rule: str,
    method: str,
    session: Mapping,
    body: Mapping,
    args,
    view_args: Mapping | None = None,
) -> str | None:
    """The reason a call is not for this chief's project, or None.

    ``method`` is the request method with HEAD already read as GET; ``body`` is one reading of the
    JSON body (``{}`` for a GET), ``args`` the query string and ``view_args`` the values the URL
    rule captured (the ``<action>`` of ``/runs/<run_id>/<action>``).
    """
    fields = ROUTE_FIELDS.get((rule, method))
    if fields is None:
        return NO_ENTRY
    own = _normalise(session.get("project_root") or "")
    source = args if method == "GET" else body

    if _foreign_root(fields, body, args, own):
        return NOT_OWN
    if _unnamed_root(fields, source, view_args or {}):
        return NOT_NAMED
    for read in fields.scopes:
        scope = _bound_scope(source, read)
        if scope is not None and not is_own(scope, own):
            return NOT_OWN
        found = _first_usable(source, read) if read.segment else None
        if found and _board(source, read) != "project" and _not_a_segment(found[1]):
            return f"{found[0]} {NOT_A_SEGMENT}"
    if _foreign_file(fields, source, own):
        return NOT_INSIDE
    return None
