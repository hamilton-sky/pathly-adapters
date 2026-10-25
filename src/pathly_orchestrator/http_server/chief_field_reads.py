"""``ROUTE_FIELDS`` entries for the GET routes a chief token gets past the route table
(chief-agent): they read the query string. See ``chief_field_types`` for what an entry says and
``chief_fields`` for the whole table.

Each entry was written from the view and the helpers it calls, and lists the query keys a chief
may send. A URL variable (``<feature>``, ``<name>``) is not a query key and is not listed.
"""

from __future__ import annotations

from .chief_field_calls import BOARD_SCOPE, BOARD_SCOPE_ONLY
from .chief_field_types import ENUM, FLAG, NAME, NUMBER, REF, TEXT, Fields, ScopeRead

_ROOT = ("project_root",)


def _reads_none(why: str) -> Fields:
    return Fields(note=f"reads no project: {why}")


_GLOBAL_SETTING = _reads_none("an app-wide setting")
_GLOBAL_DEFINITION = _reads_none("a packaged or global definition, looked up by name")
_FLEET = "fleet-wide: "
# What a chief reading a feature's detail names: the project's root narrows the feature.
_FEATURE_DETAIL = Fields(roots=_ROOT, names_root=True, under_root=("feature",))
_API_FEATURE = Fields(roots=_ROOT, under_root=("feature",))

READ_FIELDS: dict[tuple[str, str], Fields] = {
    # The board reads.
    ("/comms", "GET"): Fields(
        scopes=(BOARD_SCOPE,), keys={"limit": NUMBER, "status": ENUM, "type": ENUM}
    ),
    ("/comms/tasks", "GET"): Fields(
        scopes=(BOARD_SCOPE,), unbound=("goal_id",), keys={"ready": FLAG}
    ),
    ("/comms/goals", "GET"): Fields(scopes=(BOARD_SCOPE,)),
    ("/comms/artifacts", "GET"): Fields(
        scopes=(BOARD_SCOPE_ONLY,),
        unbound=("message_id", "goal_id"),
        keys={"limit": NUMBER, "offset": NUMBER, "order": ENUM},
    ),
    ("/comms/run/status", "GET"): Fields(scopes=(BOARD_SCOPE_ONLY,)),
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
        keys={"artifact": REF, "anchor": TEXT, "trail": TEXT},
    ),
    ("/comms/artifacts/<artifact_id>/section", "GET"): Fields(
        roots=_ROOT,
        # The row keeps the path it was stored with: the root the request names bounds it
        # (`hydrate_section(contain_in=...)`), so a chief names one.
        names_root=True,
        scopes=(ScopeRead(("scope", "feature")),),
        under_root=("artifact",),
        unbound=("artifact_id",),
        keys={"artifact": REF, "anchor": TEXT, "trail": TEXT},
    ),
    ("/hq/context", "GET"): Fields(
        roots=_ROOT,
        # `board` is a scope id: a project root for a project board, else a feature name.
        scopes=(ScopeRead(("board",)),),
        keys={"model": NAME, "sections": ENUM},
    ),
    ("/comms/goals/refs-coverage", "GET"): Fields(unbound=("goal_id",)),
    ("/comms/scope", "GET"): Fields(
        roots=_ROOT, under_root=("feature",), keys={"role": NAME}
    ),
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
    ("/db/stats/trends", "GET"): Fields(
        roots=_ROOT, names_root=True, keys={"days": NUMBER}
    ),
    ("/db/recent", "GET"): Fields(roots=_ROOT, names_root=True, keys={"limit": NUMBER}),
    ("/db/rollup", "GET"): Fields(
        roots=_ROOT,
        names_root=True,
        under_root=("feature",),
        note=_FLEET
        + "its `global` block sums every project and lists each one's root path and "
        "cost (`by_project`)",
    ),
    ("/db/features/<feature>/agents", "GET"): _FEATURE_DETAIL,
    ("/db/features/<feature>/events", "GET"): _FEATURE_DETAIL,
    ("/db/features/<feature>/otel", "GET"): _FEATURE_DETAIL,
    ("/db/features/<feature>/runs", "GET"): _FEATURE_DETAIL,
    ("/db/runs/<run_id>/cost", "GET"): Fields(unbound=("run_id",)),
    ("/db/agents", "GET"): Fields(roots=_ROOT),
    # Run reads.
    ("/runs", "GET"): Fields(roots=_ROOT, keys={"limit": NUMBER}),
    ("/runs/<run_id>", "GET"): Fields(unbound=("run_id",)),
    ("/runner/status", "GET"): Fields(unbound=("topic",)),
    ("/status", "GET"): Fields(
        roots=_ROOT,
        # No `project_root` falls back to PATHLY_PROJECT_ROOT, the server's own project.
        names_root=True,
        unbound=("topic",),
    ),
    ("/chief/session", "GET"): Fields(roots=_ROOT),
    ("/chief/presets", "GET"): Fields(roots=_ROOT),
    # The legacy /api read API: it filters by the exact `project_root` it is given.
    ("/api/agents", "GET"): Fields(roots=_ROOT),
    ("/api/features", "GET"): Fields(roots=_ROOT),
    ("/api/flows", "GET"): Fields(roots=_ROOT),
    ("/api/skills", "GET"): Fields(roots=_ROOT),
    ("/api/features/<feature>/artifacts", "GET"): _API_FEATURE,
    ("/api/features/<feature>/events", "GET"): Fields(
        roots=_ROOT, under_root=("feature",), keys={"since_seq": NUMBER}
    ),
    ("/api/features/<feature>/invocations", "GET"): _API_FEATURE,
    ("/api/features/<feature>/metrics", "GET"): _API_FEATURE,
    # `get_spans` filters by project_root and feature and ignores the run id it is given.
    ("/api/traces", "GET"): Fields(
        roots=_ROOT, under_root=("feature",), unbound=("run_id",)
    ),
    ("/flows/stage-config", "GET"): Fields(
        roots=_ROOT, under_root=("feature",), keys={"stage": NAME}
    ),
    ("/skills/abilities", "GET"): Fields(roots=_ROOT),
    ("/skills/composition", "GET"): Fields(roots=_ROOT),
    ("/skills/prompts", "GET"): Fields(
        roots=_ROOT, keys={"category": NAME, "kind": ENUM}
    ),
    ("/telemetry/trends", "GET"): Fields(
        roots=_ROOT,
        # A blank feature sums every project's cost unless project_root narrows it.
        names_root_unless=("feature",),
        unbound=("feature",),
        keys={"days": NUMBER},
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
        keys={"state": ENUM},
        note="broadcasts a packaged menu; `feature` only fills a title",
    ),
    ("/metrics", "GET"): _reads_none(_FLEET + "server-wide counters"),
    ("/metrics/json", "GET"): _reads_none(_FLEET + "server-wide counters"),
    ("/ops/export/skills", "GET"): Fields(
        keys={"adapter": ENUM}, note="reads no project: the host's installable skills"
    ),
    ("/registry/agents", "GET"): _GLOBAL_DEFINITION,
    ("/registry/skills", "GET"): _GLOBAL_DEFINITION,
    ("/skills/catalog", "GET"): _GLOBAL_DEFINITION,
    ("/skills/summary-format/<style>", "GET"): _GLOBAL_DEFINITION,
    ("/static/<path:filename>", "GET"): _reads_none("the server's own static files"),
    ("/telemetry/pricing", "GET"): _reads_none("the provider price table"),
}
