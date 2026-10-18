"""Which request fields each route reads to pick a project, for the chief gate (chief-agent).

``ROUTE_ACTIONS`` (``chief_routes``) says what a call is. This table says what it *names*: for
every route a chief token can get past the route table, the fields the view reads as a project
root, a board scope or a file, with the fallback it uses when the field is absent. The gate
applies the table with one function (``chief_project.project_refusal``), so a route that reads a
new field is one table entry, not another branch. ``tests/http_api/test_chief_gate.py`` walks
``app.url_map`` and fails when a route the chief can reach has no entry, so a route added later
cannot be added unbound.

A GET route reads its query string; every other listed route reads the JSON body (no listed view
reads ``request.args`` on a POST, and the test above checks that). ``project_root`` is also
checked wherever it appears, in the body or the query string of any route.

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
  is the project root, so it must be the chief's own; ``segment`` marks a scope the route also
  joins into a path, which must then be one folder name.
* ``paths`` / ``abs_paths`` / ``text_paths``: a file the route reads or stores. It must lie inside
  the chief's project.
* ``under_root``: a feature or other name the route reads together with ``project_root`` (its
  query filters by both), so the root the gate checks bounds it.
* ``unbound``: a feature, goal, task, message, run, topic or other id the route reads and the gate
  does not bind to the project: feature boards are keyed by name only, and the id-addressed calls
  are ticket 14's (writes) or have no ticket yet (reads). Only what is really unbound is listed
  here, so the table is the inventory.
* ``note``: why the route reads no project (it must say, if it names no field), or what it sums
  across projects whatever ``project_root`` says.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ScopeRead:
    """A board scope a route reads: the first usable value among ``keys`` (a truthy value, and a
    string that is not blank), the way the route falls back from ``scope`` to ``feature``.

    The board it applies to is the value of ``board_key`` (``feature`` when it is absent or not a
    board name), or the fixed ``board``. With neither, the scope is a bare id of unknown board:
    a value that looks like a path is a project root and is bound. The scope is bound when the
    board is ``project``; ``skip_exact`` and ``skip_prefix`` name values the route does not use
    as a scope (a ``(interactive)`` marker, the ``project`` literal of the decompose override).

    ``segment`` is for a scope the route also joins into ``<project_root>/pathly/features/<scope>``:
    on a board other than ``project`` it must be one folder name (no ``/``, ``\\``, ``:``, ``.``
    or ``..``), or the folder it makes or writes into can lie in another project.
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
    under_root: tuple[str, ...] = ()
    unbound: tuple[str, ...] = ()
    names_root: bool = False
    names_root_when: tuple[str, ...] = ()
    names_root_unless: tuple[str, ...] = ()
    names_root_verbs: tuple[str, ...] = ()
    note: str = ""

    def declared(self) -> frozenset[str]:
        """Every request field this entry names."""
        found = {*self.roots, *self.paths, *self.abs_paths, *self.unbound}
        found.update(self.under_root, self.names_root_when, self.names_root_unless)
        for read in self.scopes:
            found.update(read.keys)
            if read.board_key:
                found.add(read.board_key)
        for text in self.text_paths:
            found.update((text.path_key, text.text_key))
        return frozenset(found)


_ROOT = ("project_root",)
# `scope`, else `feature`, on the board `board` names (the feature board by default).
_BOARD_SCOPE = ScopeRead(("scope", "feature"), board_key="board")
_BOARD_SCOPE_ONLY = ScopeRead(("scope",), board_key="board")
# `/comms/run` saves an evaluator's reply under `<project_root>/pathly/features/<scope>/`.
_RUN_BOARD_SCOPE = ScopeRead(("scope",), board_key="board", segment=True)


def _reads_none(why: str) -> Fields:
    return Fields(note=f"reads no project: {why}")


_GLOBAL_SETTING = _reads_none("an app-wide setting")
_GLOBAL_DEFINITION = _reads_none("a packaged or global definition, looked up by name")
_FLEET = "fleet-wide: "

ROUTE_FIELDS: Mapping[tuple[str, str], Fields] = MappingProxyType(
    {
        # --- the calls ROUTE_ACTIONS lists: they read the JSON body ---------------------------
        ("/comms/search", "POST"): Fields(scopes=(_BOARD_SCOPE,)),
        ("/code/query", "POST"): Fields(
            roots=_ROOT,
            names_root=True,
            # The backend resolves a relative target against `project_root` (the server's working
            # directory when absent) and logs the query as a `discovery` row on the project board
            # at `scope or feature`, except for a blank or `(marker)` scope.
            scopes=(
                ScopeRead(("scope", "feature"), board="project", skip_prefix=("(",)),
            ),
            paths=("target",),
        ),
        ("/comms/post", "POST"): Fields(
            roots=_ROOT,
            # `context_refs` are resolved under `project_root`, else the server's directory.
            names_root_when=("context_refs",),
            scopes=(_BOARD_SCOPE,),
            # A path the row keeps, and `GET /comms/artifacts/<id>/section` later reads whole.
            abs_paths=("artifact_path",),
            text_paths=(TextPath("artifact_path", "text", "artifact"),),
            unbound=("goal_id", "run_id"),
        ),
        ("/comms/goals/decompose", "POST"): Fields(
            roots=_ROOT, names_root=True, unbound=("goal_id",)
        ),
        ("/comms/features/decompose", "POST"): Fields(
            roots=_ROOT,
            names_root=True,
            # The feature is the board's name (feature boards are keyed by name only, so it is not
            # bound to a project) and the folder `<project_root>/pathly/features/<feature>`, which
            # the route makes and hands to the run as its storage path: one folder name.
            scopes=(ScopeRead(("feature",), board="feature", segment=True),),
        ),
        ("/comms/project/decompose", "POST"): Fields(
            roots=_ROOT,
            names_root=True,
            # `project` overrides the scope of the project board (the literal "project" is "none").
            scopes=(ScopeRead(("project",), board="project", skip_exact=("project",)),),
        ),
        ("/comms/acknowledge", "POST"): Fields(unbound=("message_id",)),
        ("/comms/supersede", "POST"): Fields(unbound=("old_id", "new_id")),
        ("/runs", "POST"): Fields(
            roots=_ROOT,
            names_root=True,
            scopes=(_BOARD_SCOPE_ONLY,),
            unbound=("goal_id",),
        ),
        ("/comms/goals/run", "POST"): Fields(
            roots=_ROOT, names_root=True, unbound=("goal_id",)
        ),
        ("/comms/run", "POST"): Fields(
            roots=_ROOT, names_root=True, scopes=(_RUN_BOARD_SCOPE,)
        ),
        ("/comms/tasks/run", "POST"): Fields(
            roots=_ROOT, names_root=True, unbound=("message_id",)
        ),
        ("/runs/<run_id>/<action>", "POST"): Fields(
            roots=_ROOT,
            # `retry` starts a run in `body["project_root"]`, empty or not; the other verbs act on
            # the registry's run and read no directory from the body.
            names_root_verbs=("retry",),
            unbound=("run_id",),
        ),
        ("/runs/<run_id>/stop", "POST"): Fields(unbound=("run_id",)),
        ("/comms/goals/stop", "POST"): Fields(unbound=("goal_id",)),
        ("/comms/run/stop", "POST"): Fields(scopes=(_BOARD_SCOPE_ONLY,)),
        ("/comms/tasks/stop", "POST"): Fields(unbound=("message_id",)),
        ("/runner/agent-answer", "POST"): Fields(unbound=("topic",)),
        ("/comms/answer", "POST"): Fields(unbound=("question_id", "option_id")),
        # --- every GET that is not refused: they read the query string ------------------------
        # The board reads.
        ("/comms", "GET"): Fields(scopes=(_BOARD_SCOPE,)),
        ("/comms/tasks", "GET"): Fields(scopes=(_BOARD_SCOPE,), unbound=("goal_id",)),
        ("/comms/goals", "GET"): Fields(scopes=(_BOARD_SCOPE,)),
        ("/comms/artifacts", "GET"): Fields(
            scopes=(_BOARD_SCOPE_ONLY,), unbound=("message_id", "goal_id")
        ),
        ("/comms/run/status", "GET"): Fields(scopes=(_BOARD_SCOPE_ONLY,)),
        # A scope of any board (the rows trashed under it, the artifacts of it).
        ("/comms/trash", "GET"): Fields(scopes=(ScopeRead(("scope",)),)),
        ("/comms/artifacts/section", "GET"): Fields(
            roots=_ROOT,
            # Reads `<project_root or the server's directory>/pathly/...` and posts a "context
            # pull" row on the feature board `scope` when `trail` is given.
            names_root=True,
            scopes=(ScopeRead(("scope", "feature")),),
            # The artifact is looked up under `project_root`, behind the traversal guard of
            # `hydrate.safe_artifact_path`.
            under_root=("artifact",),
        ),
        ("/comms/artifacts/<artifact_id>/section", "GET"): Fields(
            roots=_ROOT,
            scopes=(ScopeRead(("scope", "feature")),),
            under_root=("artifact",),
            unbound=("artifact_id",),
        ),
        ("/hq/context", "GET"): Fields(
            roots=_ROOT,
            # `board` is a scope id: a project root for a project board, else a feature name.
            scopes=(ScopeRead(("board",)),),
        ),
        ("/comms/goals/refs-coverage", "GET"): Fields(unbound=("goal_id",)),
        ("/comms/scope", "GET"): Fields(roots=_ROOT, under_root=("feature",)),
        ("/comms/permissions", "GET"): Fields(roots=_ROOT),
        # The /db read API: a project filter that falls back to PATHLY_PROJECT_ROOT, else to
        # every project. The chief names its own. `/db/rollup`'s `global` block sums every
        # project whatever the filter says (fleet-wide), and `/db/runs/<id>/cost` is by run id.
        ("/db/features", "GET"): Fields(roots=_ROOT, names_root=True),
        ("/db/stats", "GET"): Fields(
            roots=_ROOT,
            names_root=True,
            note=_FLEET
            + "its `features`, `events` and `invocations` counts are global (every project); "
            "only the token and cost totals follow project_root",
        ),
        ("/db/stats/trends", "GET"): Fields(roots=_ROOT, names_root=True),
        ("/db/recent", "GET"): Fields(roots=_ROOT, names_root=True),
        ("/db/rollup", "GET"): Fields(
            roots=_ROOT,
            names_root=True,
            under_root=("feature",),
            note=_FLEET + "its `global` block sums every project",
        ),
        ("/db/features/<feature>/agents", "GET"): Fields(
            roots=_ROOT, names_root=True, under_root=("feature",)
        ),
        ("/db/features/<feature>/events", "GET"): Fields(
            roots=_ROOT, names_root=True, under_root=("feature",)
        ),
        ("/db/features/<feature>/otel", "GET"): Fields(
            roots=_ROOT, names_root=True, under_root=("feature",)
        ),
        ("/db/features/<feature>/runs", "GET"): Fields(
            roots=_ROOT, names_root=True, under_root=("feature",)
        ),
        ("/db/runs/<run_id>/cost", "GET"): Fields(unbound=("run_id",)),
        ("/db/agents", "GET"): Fields(roots=_ROOT),
        # Run reads.
        ("/runs", "GET"): Fields(roots=_ROOT),
        ("/runs/<run_id>", "GET"): Fields(unbound=("run_id",)),
        ("/runner/status", "GET"): Fields(unbound=("topic",)),
        ("/status", "GET"): Fields(
            roots=_ROOT,
            # No `project_root` falls back to PATHLY_PROJECT_ROOT, the server's own project.
            names_root=True,
            unbound=("topic",),
        ),
        ("/chief/session", "GET"): Fields(roots=_ROOT),
        # The legacy /api read API: it filters by the exact `project_root` it is given.
        ("/api/agents", "GET"): Fields(roots=_ROOT),
        ("/api/features", "GET"): Fields(roots=_ROOT),
        ("/api/flows", "GET"): Fields(roots=_ROOT),
        ("/api/skills", "GET"): Fields(roots=_ROOT),
        ("/api/features/<feature>/artifacts", "GET"): Fields(
            roots=_ROOT, under_root=("feature",)
        ),
        ("/api/features/<feature>/events", "GET"): Fields(
            roots=_ROOT, under_root=("feature",)
        ),
        ("/api/features/<feature>/invocations", "GET"): Fields(
            roots=_ROOT, under_root=("feature",)
        ),
        ("/api/features/<feature>/metrics", "GET"): Fields(
            roots=_ROOT, under_root=("feature",)
        ),
        # `get_spans` filters by project_root and feature and ignores the run id it is given.
        ("/api/traces", "GET"): Fields(
            roots=_ROOT, under_root=("feature",), unbound=("run_id",)
        ),
        ("/flows/stage-config", "GET"): Fields(roots=_ROOT, under_root=("feature",)),
        ("/skills/abilities", "GET"): Fields(roots=_ROOT),
        ("/skills/composition", "GET"): Fields(roots=_ROOT),
        ("/skills/prompts", "GET"): Fields(roots=_ROOT),
        ("/telemetry/trends", "GET"): Fields(
            roots=_ROOT,
            # A blank feature sums every project's cost unless project_root narrows it.
            names_root_unless=("feature",),
            unbound=("feature",),
            note=_FLEET + "a named feature is summed across every project",
        ),
        # Reads that name no project.
        ("/catalog/all", "GET"): _GLOBAL_DEFINITION,
        ("/catalog/content", "GET"): Fields(
            unbound=("path",),
            note="looks a catalog row up by its path, never opens the file",
        ),
        ("/comms/default-progress", "GET"): _GLOBAL_SETTING,
        ("/comms/default-selection", "GET"): _GLOBAL_SETTING,
        ("/comms/default-style", "GET"): _GLOBAL_SETTING,
        ("/comms/logging-config", "GET"): _GLOBAL_SETTING,
        ("/comms/model-policy", "GET"): _GLOBAL_SETTING,
        ("/flows", "GET"): _GLOBAL_DEFINITION,
        ("/flows/", "GET"): _GLOBAL_DEFINITION,
        ("/flows/<name>/graph", "GET"): _GLOBAL_DEFINITION,
        ("/flows/<path:name>", "GET"): _GLOBAL_DEFINITION,
        ("/health", "GET"): _reads_none("server health"),
        ("/hq/actions", "GET"): _reads_none("the operator action catalog"),
        ("/menu/<name>", "GET"): Fields(
            unbound=("feature",),
            note="broadcasts a packaged menu; `feature` only fills a title",
        ),
        ("/metrics", "GET"): _reads_none(_FLEET + "server-wide counters"),
        ("/metrics/json", "GET"): _reads_none(_FLEET + "server-wide counters"),
        ("/ops/export/skills", "GET"): _reads_none("the host's installable skills"),
        ("/registry/agents", "GET"): _GLOBAL_DEFINITION,
        ("/registry/skills", "GET"): _GLOBAL_DEFINITION,
        ("/skills/catalog", "GET"): _GLOBAL_DEFINITION,
        ("/skills/summary-format/<style>", "GET"): _GLOBAL_DEFINITION,
        ("/static/<path:filename>", "GET"): _reads_none(
            "the server's own static files"
        ),
        ("/telemetry/pricing", "GET"): _reads_none("the provider price table"),
    }
)
