"""Which project an id a chief names belongs to (chief-agent 14).

``chief_project`` binds what a request names as a place: a root, a scope, a file. Some writes name
their target by id and carry none of those, so a chief could pause or abort another project's run,
or acknowledge, supersede, run or stop another project's message, goal or task. ``ROUTE_FIELDS``
lists those ids (``run_ids``, ``stamped_run_ids``, ``row_ids``) and ``target_in_project`` looks
each one up, for a chief token only (the gate calls it after the action check).

* A **run** (``run_ids``, the ``<run_id>`` of the run-control routes) is placed by the project root
  ``run_history`` recorded for it, else the root of a registry entry (any status), else the board
  its board lock is held on. A run no source knows is refused: a chief never acts on a run it
  cannot place. ``stamped_run_ids`` (the ``run_id`` a ``/comms/post`` row carries) are only a
  correlation stamp, so there an unknown id passes (a chief's own session run is one) and only a
  run placed in another project is refused.
* A **message** (``row_ids``; a goal and a task are ``comms_messages`` rows too, and the goal
  decomposer later reads the ``scope`` of the goal's row) is placed by the ``board`` and ``scope``
  of its row, deleted or not. A ``project`` row is the project's when its scope is the session's
  root, spelled as ``chief_project`` accepts it (``is_own``): the scope of a project board is its
  root. A ``feature`` row is the project's when its scope is one plain folder name and a folder of
  that name exists under ``<root>/pathly/features/`` or ``<root>/pathly/features/.archive/``. A
  feature scope is a name, not a path, and feature boards are keyed by name only: two projects
  that both have a feature ``demo`` share the board, so the folder check is the best this can do.
  A ``global`` row, and any other board, is no project's, so no write may name it. An id no row
  has passes, and the route answers it (404 for most).

An id that is not a string, is too long or holds a control character cannot be looked up and is
refused; a blank one names nothing and is left to the route's 400. ``view_args`` are read for a
URL variable and the body for any other key, so a body key can never stand in for the URL's.
The imports of ``db`` and ``supervisor`` are inside the functions, per the layer rule.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Mapping

from pathly_orchestrator.scope_names import is_segment, root_spelling

from .chief_field_types import url_variables
from .chief_fields import ROUTE_FIELDS
from .chief_project import is_own

NOT_IN_PROJECT = "not in this chief's project"
MAX_ID = 512
ARCHIVE = ".archive"


def is_id(value: object) -> bool:
    """True for a string a lookup can take: not blank, at most ``MAX_ID`` long, and no control
    character or lone surrogate (SQLite cannot be handed the second, and the first is no id).
    """
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= MAX_ID
        and not any(unicodedata.category(c) in ("Cc", "Cs") for c in value)
    )


def _has_feature(scope: object, own: str) -> bool:
    """True when ``scope`` is one folder name that is a feature of the project ``own``."""
    if not is_segment(scope) or scope == ARCHIVE:
        return False
    features = os.path.join(own, "pathly", "features")
    return any(
        os.path.isdir(os.path.join(base, str(scope)))
        for base in (features, os.path.join(features, ARCHIVE))
    )


def _in_project(board: object, scope: object, own: str | None) -> bool:
    """True when the board ``board`` holds under ``scope`` is the project ``own``'s."""
    if own is None:
        return False
    kind = board or "feature"  # the routes read `row["board"] or "feature"`
    if kind == "project":
        return is_own(scope, own)
    return kind == "feature" and _has_feature(scope, own)


def _row_in_project(conn, message_id: str, own: str | None) -> bool:
    from pathly_orchestrator.db.queries.placement import message_board_scope

    found = message_board_scope(conn, message_id)
    return found is None or _in_project(found[0], found[1], own)


def _placed_run(conn, run_id: str, own: str | None) -> bool | None:
    """True or False when a source places the run in or out of the project, None when none does."""
    from pathly_orchestrator.db.queries.placement import run_project_root
    from pathly_orchestrator.supervisor import board_lock

    from .blueprints.control._helpers import find_registry_run

    root = run_project_root(conn, run_id)
    if root is not None:
        return is_own(root, own)
    live = find_registry_run(run_id, statuses=None)
    if live is not None:
        return is_own(getattr(live[1], "project_root", None), own)
    held = board_lock.find_by_holder(run_id)
    if held is not None:
        return _in_project(held[0], held[1], own)
    return None


def _acted_run(conn, run_id: str, own: str | None) -> bool:
    return _placed_run(conn, run_id, own) is True


def _stamped_run(conn, run_id: str, own: str | None) -> bool:
    return _placed_run(conn, run_id, own) is not False


def target_in_project(
    conn, session: Mapping, rule: str, body: Mapping, view_args: Mapping
) -> bool | None:
    """Whether the ids a chief's call names are in its project: True when every one is, False when
    any is not (the gate answers 403), None when the route names none.

    ``rule`` is the URL rule of a POST, ``body`` one reading of the JSON body and ``view_args``
    the values the rule captured. The ids and how each is placed are in the route's
    ``ROUTE_FIELDS`` entry.
    """
    fields = ROUTE_FIELDS.get((rule, "POST"))
    if fields is None:
        return None
    own = root_spelling(session.get("project_root"))
    in_url = url_variables(rule)
    verdicts: list[bool] = []
    for keys, place in (
        (fields.run_ids, _acted_run),
        (fields.stamped_run_ids, _stamped_run),
        (fields.row_ids, _row_in_project),
    ):
        for key in keys:
            value = view_args.get(key) if key in in_url else body.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue  # names nothing: the route validates the field
            verdicts.append(is_id(value) and place(conn, value, own))
    return all(verdicts) if verdicts else None
