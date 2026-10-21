"""What a ``ROUTE_FIELDS`` entry can say about the request a route reads (chief-agent).

``ROUTE_FIELDS`` (``chief_fields``) has one ``Fields`` entry per route a chief token can get past
the route table. The gate applies an entry with two functions: ``chief_project.project_refusal``
(which project the request names) and ``chief_keys.key_refusal`` (which keys it may send). A GET
route reads its query string; every other listed route reads the JSON body (no listed view reads
``request.args`` on a POST, and a test checks that). ``project_root`` is also checked wherever it
appears, in the body or the query string of any route, and is on every list.

**The list of keys.** An entry is the complete list of the keys a chief may send to its route:
the keys named by the attributes below, plus ``keys``. A key a chief sends that is not on it is
refused, with the key named. A key the route reads and no chief flow needs is not listed; it is in
``not_for_chief``, so a test can tell "deliberately absent" from "forgotten". A URL variable
(``<run_id>`` in the rule) is not a key and is not on the list. Every listed key has a kind
(``kinds()``), and a test reads them: free text, number, flag, enum, name, id, or one of the kinds
that can reach a file or a folder (root, scope, segment, path, ref, flow, skill), each of which has
a rule the gate applies and, where the key reaches a sink, the sink applies too (a ``ref`` is the
one the gate cannot judge: ``hydrate.safe_artifact_path`` resolves it under the root the request
names, which the gate makes it name).

What an entry can say:

* ``roots``: the route reads ``project_root``. Whatever it holds must be the chief's own project.
* ``names_root``: the route falls back to something else when ``project_root`` is absent (the
  server's working directory or ``PATHLY_PROJECT_ROOT``, or every project), so the chief must
  name its own. ``names_root_when`` does the same only when one of those keys is present,
  ``names_root_unless`` only when none of those keys is given a usable value (``/telemetry/trends``
  sums every project unless it is given a feature), and ``names_root_verbs`` only for the
  ``<action>`` verbs listed (``/runs/<run_id>/retry`` starts a run in the directory its body names;
  the other verbs act on the run's own state).
* ``scopes``: a board scope the route reads (see ``ScopeRead``). On the project board the scope
  is the project root, so it must be the chief's own. On any other board a scope that is a path
  is a project root to the board mirror (it writes ``<scope>/pathly/project/BOARD.json``), so it
  must be the chief's own too, and any other scope is one folder name; ``segment`` marks a scope
  the route also joins into a folder it makes, which must then be one folder name even when it
  is the chief's own root.
* ``segments``: a field the route stores and the server later joins into a folder name (the
  ``slug`` of a goal post, which the goal run and decompose make ``goals/<slug>`` of). One
  folder name: no ``/``, ``\\``, ``:`` or ``..``.
* ``paths`` / ``abs_paths`` / ``text_paths``: a file the route reads or stores. It must lie inside
  the chief's project.
* ``flows`` / ``skills``: a flow or a skill the route names. A flow is read from the packaged
  ``core/flows`` (or the database) and a goal run makes a folder of it; a skill is read from the
  packaged ``core/skills``. One name each (``scope_names.is_flow_name`` / ``is_skill_name``), which
  the readers apply as well.
* ``under_root``: a feature or other name the route reads together with ``project_root`` (its
  query filters by both), so the root the gate checks bounds it.
* ``run_ids`` / ``stamped_run_ids`` / ``row_ids``: an id of a write that ``chief_bind`` binds to the
  chief's project (the key is a URL variable, or a key of the body). ``run_ids`` name a run the
  route acts on (``/runs/<run_id>/stop``): refused unless the run history, the registry or the
  board lock places it in the project. ``stamped_run_ids`` name a run the route only stores on
  the row it makes (the ``run_id`` of ``/comms/post``): refused when a source places the run
  elsewhere, passed when none knows it. ``row_ids`` name a ``comms_messages`` row (a goal and a
  task are rows too): refused when its board and scope are not the project's, passed when no row
  has the id. They are ID keys like ``unbound`` ones, so the key list still holds them.
* ``unbound``: an id or name the route reads and the gate does not bind to the project. What is
  left is the id a GET reads (no ticket binds the reads yet), a feature name (feature boards are
  keyed by name only), the ``topic`` of ``/runner/agent-answer`` (the cite rule, ``chief_cite``,
  checks that run's project) and the ``option_id`` of ``/comms/answer`` (the cite rule refuses it
  to a chief). Only what is really unbound is listed here, so the table is the inventory.
* ``keys``: every other key the route reads and a chief may send, with its kind. It also gives the
  kind of a key another attribute names, when that is more exact (``artifact`` is a path).
* ``not_for_chief``: keys the route reads and a chief may not send.
* ``note``: why the route reads no project (it must say, if it names no field), or what it sums
  across projects whatever ``project_root`` says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- the kind of a key ---------------------------------------------------------------------
# Kinds that name no file: the gate only checks that the key is on the list.
TEXT = "text"  # prose the route stores or hands to an agent
NUMBER = "number"
FLAG = "flag"  # a boolean, or a map of booleans
ENUM = "enum"  # one of a few words the route checks
NAME = "name"  # a role, an engine, a model, a state: looked up by name, never joined into a path
ID = "id"  # the id of a row, a run or a topic, looked up
# Kinds that can reach a file or a folder: the gate has a rule for each (and so has the sink).
ROOT = "root"  # a project root
SCOPE = "scope"  # a board scope: the project's root, or one folder name
SEGMENT = "segment"  # one folder name the server makes a folder of
PATH = "path"  # a file inside the project
REF = "ref"  # a file ref the sink resolves under the root the request names
FLOW = "flow"  # a flow's name
SKILL = "skill"  # a skill's name

PLAIN_KINDS = frozenset({TEXT, NUMBER, FLAG, ENUM, NAME, ID})
FILE_KINDS = frozenset({ROOT, SCOPE, SEGMENT, PATH, REF, FLOW, SKILL})
KINDS = PLAIN_KINDS | FILE_KINDS

_URL_VARIABLE = re.compile(r"<(?:[^<>:]+:)?([^<>]+)>")


def url_variables(rule: str) -> frozenset[str]:
    """The names a URL rule captures (``<run_id>``, ``<path:name>``): not request keys."""
    return frozenset(_URL_VARIABLE.findall(rule))


@dataclass(frozen=True)
class ScopeRead:
    """A board scope a route reads: the first usable value among ``keys`` (a truthy value, and a
    string that is not blank), the way the route falls back from ``scope`` to ``feature``.

    The board it applies to is the value of ``board_key`` (``feature`` when it is absent or not a
    board name), or the fixed ``board``. With neither, the scope is a bare id of unknown board:
    a value that looks like a path is a project root and is bound. The scope is bound when the
    board is ``project``; ``skip_exact`` and ``skip_prefix`` name values the route does not use
    as a scope (a ``(interactive)`` marker, the ``project`` literal of the decompose override).

    On a board other than ``project`` a scope that is a path (``/``, ``\\`` or a drive prefix)
    must still be the chief's own root, because the board mirror reads such a scope as a project
    root whatever board the row was posted to, and any other scope must be one folder name.
    ``segment`` is for a scope the route also joins into ``<project_root>/pathly/features/<scope>``:
    on a board other than ``project`` it must be one folder name (no ``/``, ``\\``, ``:``, ``.``
    or ``..``) even when it is the chief's own root, or the folder it makes or writes into can lie
    in another project.
    """

    keys: tuple[str, ...]
    board_key: str | None = None
    board: str | None = None
    skip_exact: tuple[str, ...] = ()
    skip_prefix: tuple[str, ...] = ()
    segment: bool = False


@dataclass(frozen=True)
class TextPath:
    """A file path the route recovers from prose: ``text_key`` of a body whose ``type`` is
    ``when_type`` and whose ``path_key`` is blank (``/comms/post`` of an ``artifact``).
    """

    path_key: str
    text_key: str
    when_type: str


@dataclass(frozen=True)
class Fields:
    roots: tuple[str, ...] = ()
    scopes: tuple[ScopeRead, ...] = ()
    paths: tuple[str, ...] = ()
    abs_paths: tuple[str, ...] = ()
    text_paths: tuple[TextPath, ...] = ()
    segments: tuple[str, ...] = ()
    flows: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    under_root: tuple[str, ...] = ()
    run_ids: tuple[str, ...] = ()
    stamped_run_ids: tuple[str, ...] = ()
    row_ids: tuple[str, ...] = ()
    unbound: tuple[str, ...] = ()
    keys: dict[str, str] = field(default_factory=dict)
    not_for_chief: tuple[str, ...] = ()
    names_root: bool = False
    names_root_when: tuple[str, ...] = ()
    names_root_unless: tuple[str, ...] = ()
    names_root_verbs: tuple[str, ...] = ()
    note: str = ""

    def kinds(self) -> dict[str, str]:
        """Every key this entry lists, with its kind (``keys`` has the last word)."""
        found: dict[str, str] = {}
        found.update(
            dict.fromkeys((*self.names_root_when, *self.names_root_unless), TEXT)
        )
        found.update(dict.fromkeys(self.under_root, NAME))
        found.update(
            dict.fromkeys((*self.run_ids, *self.stamped_run_ids, *self.row_ids), ID)
        )
        found.update(dict.fromkeys(self.unbound, ID))
        found.update(dict.fromkeys(self.roots, ROOT))
        for read in self.scopes:
            found.update(dict.fromkeys(read.keys, SEGMENT if read.segment else SCOPE))
            if read.board_key:
                found[read.board_key] = ENUM
        found.update(dict.fromkeys((*self.paths, *self.abs_paths), PATH))
        for text in self.text_paths:
            found[text.path_key] = PATH
            found[text.text_key] = TEXT
        found.update(dict.fromkeys(self.segments, SEGMENT))
        found.update(dict.fromkeys(self.flows, FLOW))
        found.update(dict.fromkeys(self.skills, SKILL))
        found.update(self.keys)
        return found

    def declared(self) -> frozenset[str]:
        """Every request field this entry names."""
        return frozenset(self.kinds())

    def allowed(self, rule: str = "") -> frozenset[str]:
        """The keys a chief may send to the route ``rule``: the listed ones, minus the names its
        URL captures, plus ``project_root``, which the gate checks on every route.
        """
        return frozenset({*self.kinds(), "project_root"}) - url_variables(rule)
