"""``ROUTE_FIELDS`` entries for the calls ``ROUTE_ACTIONS`` lists (chief-agent): they read the JSON
body. See ``chief_field_types`` for what an entry says and ``chief_fields`` for the whole table.

Each entry was written from the view and every helper it calls, and lists the body keys a chief
may send. The keys a view reads and no chief flow needs are in ``not_for_chief``: ``ability_ids``
(composition packs picked in Studio), ``system_prompt`` and ``interactive`` of ``/comms/run``, the
client-drop switches of ``/comms/post``, and the ``flow`` of ``/comms/goals/run`` (the goal's
executor picks the flow; a chief that wants another one starts it with ``POST /runs``).
"""

from __future__ import annotations

from .chief_field_types import (
    ENUM,
    FLAG,
    ID,
    NAME,
    NUMBER,
    REF,
    TEXT,
    Fields,
    ScopeRead,
    TextPath,
)

_ROOT = ("project_root",)
# `scope`, else `feature`, on the board `board` names (the feature board by default).
BOARD_SCOPE = ScopeRead(("scope", "feature"), board_key="board")
BOARD_SCOPE_ONLY = ScopeRead(("scope",), board_key="board")
# `/comms/run` saves an evaluator's reply under `<project_root>/pathly/features/<scope>/`.
_RUN_BOARD_SCOPE = ScopeRead(("scope",), board_key="board", segment=True)

# The keys a run or a decompose start reads to pick its engine and how chatty it is.
_ENGINE = {"adapter": NAME, "model": NAME}
_RUN = {**_ENGINE, "progress": ENUM}
# Verbatim prompt text for the agents a call starts (these also need the `run` action).
_PROMPT = {"prompt_override": TEXT}
_STAGES = {"stage_overrides": TEXT}  # a {state: prompt text} map
# The answer routes carry the id of the human message they cite (`chief_cite` reads it).
_CITE = {"cite": ID}

CALL_FIELDS: dict[tuple[str, str], Fields] = {
    ("/comms/search", "POST"): Fields(
        scopes=(BOARD_SCOPE,),
        keys={"query": TEXT, "k": NUMBER, "mode": ENUM},
    ),
    ("/code/query", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        # The backend resolves a relative target against `project_root` (the server's working
        # directory when absent) and logs the query as a `discovery` row on the project board
        # at `scope or feature`, except for a blank or `(marker)` scope.
        scopes=(ScopeRead(("scope", "feature"), board="project", skip_prefix=("(",)),),
        paths=("target",),
        keys={"op": ENUM, "role": NAME, "engine": ENUM, "budget": NUMBER},
    ),
    ("/comms/post", "POST"): Fields(
        roots=_ROOT,
        # `context_refs` are resolved under `project_root`, else the server's directory.
        names_root_when=("context_refs",),
        scopes=(BOARD_SCOPE,),
        # A path the row keeps, and `GET /comms/artifacts/<id>/section` later reads whole.
        abs_paths=("artifact_path",),
        text_paths=(TextPath("artifact_path", "text", "artifact"),),
        # A goal's `slug` is stored as sent and becomes the folder `goals/<slug>`.
        segments=("slug",),
        # The goal the row belongs to and the run it is stamped with (`chief_bind`): another
        # project's is refused, and a run no source knows is not (the chief's own run id).
        row_ids=("goal_id",),
        stamped_run_ids=("run_id",),
        keys={
            "from": NAME,
            "type": ENUM,
            "text": TEXT,
            "to": NAME,
            "options": TEXT,
            "reply_to": ID,
            "stage": NAME,
            "conv": NUMBER,
            "depends_on": ID,
            "supersedes": ID,
            "lane": NAME,
            "files": TEXT,  # a task's declared footprint: compared as text, never opened
            "executor": ENUM,
            "artifact_type": ENUM,
            "summary": TEXT,
            "no_refs": TEXT,
            "context_refs": REF,
        },
        not_for_chief=("summary_backend", "embed_summary"),
    ),
    ("/comms/goals/decompose", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        row_ids=("goal_id",),
        keys={"mode": ENUM, **_RUN, **_PROMPT, **_STAGES},
        not_for_chief=("ability_ids",),
    ),
    ("/comms/features/decompose", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        # The feature is the board's name (feature boards are keyed by name only, so it is not
        # bound to a project) and the folder `<project_root>/pathly/features/<feature>`, which
        # the route makes and hands to the run as its storage path: one folder name.
        scopes=(ScopeRead(("feature",), board="feature", segment=True),),
        keys={"rigor": ENUM, **_ENGINE, **_STAGES},
    ),
    ("/comms/project/decompose", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        # `project` overrides the scope of the project board (the literal "project" is "none").
        scopes=(ScopeRead(("project",), board="project", skip_exact=("project",)),),
        keys={"rigor": ENUM, **_ENGINE, **_STAGES},
    ),
    ("/comms/acknowledge", "POST"): Fields(
        row_ids=("message_id",), keys={"agent": NAME, **_CITE}
    ),
    ("/comms/supersede", "POST"): Fields(row_ids=("old_id", "new_id")),
    # A standing order on the project board of `project_root`; the route answers 400 for a
    # body that names none, so there is no other project to fall back to.
    ("/comms/directives", "POST"): Fields(
        roots=_ROOT, keys={"to_agent": NAME, "text": TEXT}
    ),
    ("/runs", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        scopes=(BOARD_SCOPE_ONLY,),
        # `kind=flow` starts the flow named here (`start_run` reads `core/flows/<flow>`).
        flows=("flow",),
        row_ids=("goal_id",),
        # The cap a flow start runs with (`chief_budget` holds it to the session's ceiling).
        keys={"kind": ENUM, "max_cost_usd": NUMBER, **_ENGINE},
    ),
    ("/comms/goals/run", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        row_ids=("goal_id",),
        keys={"executor": ENUM, **_RUN, **_PROMPT, **_STAGES},
        # The `team` executor makes `pathly/features/<scope>/<flow>/<slug>` of the flow.
        not_for_chief=("flow", "ability_ids"),
    ),
    ("/comms/run", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        scopes=(_RUN_BOARD_SCOPE,),
        # The skill is read from the packaged `core/skills` into the agent's prompt.
        skills=("skill",),
        keys={
            "mode": ENUM,
            "instructions": TEXT,
            "agent": NAME,
            **_RUN,
            **_PROMPT,
        },
        not_for_chief=("system_prompt", "ability_ids", "interactive"),
    ),
    ("/comms/tasks/run", "POST"): Fields(
        roots=_ROOT,
        names_root=True,
        row_ids=("message_id",),
        keys={**_RUN, **_PROMPT},
        not_for_chief=("ability_ids",),
    ),
    ("/runs/<run_id>/<action>", "POST"): Fields(
        roots=_ROOT,
        # `retry` starts a run in `body["project_root"]`, empty or not; the other verbs act on
        # the registry's run and read no directory from the body.
        names_root_verbs=("retry",),
        run_ids=("run_id",),
        # `reroute` reads the engine (and echoes `stage`); `retry` starts the run again.
        flows=("flow",),
        keys={
            **_ENGINE,
            "stage": NAME,
            "max_iterations": NUMBER,
            "max_cost_usd": NUMBER,
            "timeout": NUMBER,
            "autonomy": FLAG,
        },
    ),
    ("/runs/<run_id>/stop", "POST"): Fields(run_ids=("run_id",)),
    ("/comms/goals/stop", "POST"): Fields(row_ids=("goal_id",)),
    ("/comms/run/stop", "POST"): Fields(scopes=(BOARD_SCOPE_ONLY,)),
    ("/comms/tasks/stop", "POST"): Fields(row_ids=("message_id",)),
    ("/runner/agent-answer", "POST"): Fields(
        unbound=("topic",), keys={"answer": TEXT, **_CITE}
    ),
    ("/comms/answer", "POST"): Fields(
        row_ids=("question_id",),
        # Refused to a chief by the cite rule, which relays a human message's own words.
        unbound=("option_id",),
        keys={"answer": TEXT, **_CITE},
    ),
}
