"""Which project a chief's request names, and whether it is the session's (chief-agent).

``project_refusal`` applies ``chief_fields.ROUTE_FIELDS`` to one request: the fields its route
reads as a project root, a board scope or a file, read from the JSON body of a POST and from the
query string of a GET, the way the view reads them. A value is the chief's own when it is a
string that ``scope_names.root_spelling`` spells as the session's root (trailing slashes
dropped, and on a host where a backslash separates, Windows, backslashes read as slashes; on any
other host a backslash is a file-name character, so a value that has one is never the chief's own);
anything else, a non-string included, is not. A file is the chief's own when it lies under that
root after its ``..`` segments are collapsed (``scope_names.lies_under``, text only: a Windows
drive letter is compared as written) and the path the route will open, resolved the way ``open``
does (symlinks followed, ``hydrate_helpers.inside_root``), still lies under the real root. A
scope that is a path (a ``/``, a ``\\`` or a drive prefix) is a project root whatever board it is
posted to, because the board mirror reads it as one, so it must be the chief's own on every
board; any other scope off the project board, a scope marked ``segment`` (the route makes a
folder of it, so even the chief's own root is refused) and a ``segments`` field (a goal's
``slug``) are one folder name: no separator, no drive colon, not ``.`` or ``..``
(``scope_names.is_segment``, the predicate the board mirror applies).

A route with no entry is refused, so a route added without one is not passed by default.
"""

from __future__ import annotations

import os
import re
from typing import Mapping

from pathly_orchestrator.scope_names import (
    host_path,
    is_segment,
    lies_under,
    root_spelling,
)

from .chief_field_types import Fields, ScopeRead, TextPath
from .chief_fields import ROUTE_FIELDS

ROOT_KEY = "project_root"
_BOARDS = ("feature", "project", "global")
_DRIVE = re.compile(r"^[A-Za-z]:")

NOT_OWN = "that is not this chief's project"
NOT_NAMED = "a chief names its project_root on this route"
NOT_INSIDE = "a chief names only files inside its project"
NOT_A_SEGMENT = "must be one folder name: no '/', '\\', ':' or '..'"
NO_ENTRY = "the gate has no project entry for this route"


def is_own(value: object, own: str | None) -> bool:
    """True when ``value`` is spelled as the root ``own`` (a ``root_spelling``; None binds
    nothing)."""
    spelled = root_spelling(value)
    return spelled is not None and spelled == own


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


def _skipped(value: object, read: ScopeRead) -> bool:
    """True for a value the route does not use as a scope (a ``(marker)``, a literal)."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text in read.skip_exact or text.startswith(read.skip_prefix)


def _scope_refusal(source: Mapping, read: ScopeRead, own: str | None) -> str | None:
    """The reason the scope a route takes from ``source`` is not for this chief's project."""
    found = _first_usable(source, read)
    if found is None or _skipped(found[1], read):
        return None
    key, value = found
    board = _board(source, read)
    if read.segment and board != "project" and not is_segment(value):
        return f"{key} {NOT_A_SEGMENT}"
    if board == "project" or not isinstance(value, str) or _path_like(value):
        # The project board's scope is its root; a path on any board is a root to the mirror.
        return None if is_own(value, own) else NOT_OWN
    return None if is_segment(value) else f"{key} {NOT_A_SEGMENT}"


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


def _foreign_root(fields: Fields, body: Mapping, args, own: str | None) -> bool:
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


def _opens_inside(value: str, own: str | None) -> bool:
    """True when ``value``, opened the way the route opens it (a relative one under the root),
    resolves to a place under the real root: a symlink inside the project that points out of it,
    or a ``..`` after such a link, is not. A path that does not exist yet resolves as far as it
    can. Fails closed.
    """
    from pathly_orchestrator.runner.hydrate_helpers import inside_root

    text = host_path(value)
    if not own or text is None:
        return False
    try:
        return inside_root(
            text if os.path.isabs(text) else os.path.join(own, text), own
        )
    except (OSError, ValueError):
        return False


def _foreign_file(fields: Fields, source: Mapping, own: str | None) -> bool:
    """A file the route reads or stores that lies outside the chief's project."""
    for keys, anchored in ((fields.paths, True), (fields.abs_paths, False)):
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                if not lies_under(value, own, anchored) or not _opens_inside(
                    value, own
                ):
                    return True
    for text_read in fields.text_paths:
        value = _recovered_path(source, text_read)
        if value is not None and not lies_under(value, own, False):
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
    own = root_spelling(session.get("project_root"))
    source = args if method == "GET" else body

    if _foreign_root(fields, body, args, own):
        return NOT_OWN
    if _unnamed_root(fields, source, view_args or {}):
        return NOT_NAMED
    for read in fields.scopes:
        refusal = _scope_refusal(source, read, own)
        if refusal is not None:
            return refusal
    for key in fields.segments:
        if _usable(source.get(key)) and not is_segment(source.get(key)):
            return f"{key} {NOT_A_SEGMENT}"
    if _foreign_file(fields, source, own):
        return NOT_INSIDE
    return None
