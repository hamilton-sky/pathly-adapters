"""The HQ operator's action catalog (pathly/features/local-operator, tickets 01-02).

The only things HQ's local model can ever propose. Two levels choose from it:
Settings picks which catalog actions HQ may use at all (``hq.actions.available``),
and the composer ticks up to MAX_ENABLED of those for the next question
(``enabled_actions`` on ``POST /hq/prompt``). Both are enforced here, on the
server. Anything not in CATALOG — answering agent questions, directives,
settings, secrets, files, shell (NEVER_OFFERED) — cannot be enabled at all.

The model only PROPOSES: a call becomes a confirm card in the chat and runs when
the user clicks Run (``POST /hq/actions/run``). Pure — no DB, no Flask.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

MAX_ENABLED = 8

CHANGES = "changes state"
SPENDS = "spends $"
HARD_TO_UNDO = "hard to undo"

# Shown to the model and documented here so a reviewer can see what is
# deliberately absent. None of these names may ever appear in CATALOG.
NEVER_OFFERED = frozenset(
    {
        "answer_question",
        "post_directive",
        "retire_directive",
        "update_settings",
        "set_secret",
        "run_shell",
        "write_file",
        "delete_file",
    }
)


class TooManyActions(ValueError):
    """More than MAX_ENABLED actions were requested for one question."""


@dataclass(frozen=True)
class HqAction:
    name: str
    domain: str  # "runs" | "board" | "artifacts"
    label: str  # Settings / composer row: "Pause a run"
    risk: tuple[str, ...]
    description: str  # what the model is told the function does
    params: dict  # JSON-schema properties; every one is required
    runs_on: str  # "server" executes it; "studio" runs it in the app
    default_available: bool


_RUN_ID = {
    "type": "string",
    "description": "The run id exactly as the packet shows it after 'run '.",
}
_GOAL = {
    "type": "string",
    "description": "The goal's id from the packet's '(id …)', or its exact title.",
}
_ARTIFACT = {
    "type": "string",
    "description": "The artifact's id from the packet's '(id …)', or its exact title.",
}

CATALOG: tuple[HqAction, ...] = (
    HqAction(
        "pause_run",
        "runs",
        "Pause a run",
        (CHANGES,),
        "Propose pausing a running flow run. Board and goal runs cannot pause.",
        {"run_id": _RUN_ID},
        "server",
        True,
    ),
    HqAction(
        "resume_run",
        "runs",
        "Resume a run",
        (CHANGES,),
        "Propose resuming a paused flow run.",
        {"run_id": _RUN_ID},
        "server",
        True,
    ),
    HqAction(
        "retry_run",
        "runs",
        "Retry a finished run",
        (CHANGES, SPENDS),
        "Propose restarting a finished, failed or stopped flow run from where it stopped.",
        {"run_id": _RUN_ID},
        "server",
        True,
    ),
    HqAction(
        "stop_run",
        "runs",
        "Stop a run",
        (CHANGES, HARD_TO_UNDO),
        "Propose stopping an active run of any kind.",
        {"run_id": _RUN_ID},
        "server",
        True,
    ),
    HqAction(
        "run_goal",
        "runs",
        "Run a goal",
        (CHANGES, SPENDS),
        "Propose starting a goal's task DAG with the goal's own executor "
        "(spawns cloud agents).",
        {"goal": _GOAL},
        "server",
        False,
    ),
    HqAction(
        "plan_goal",
        "runs",
        "Plan a goal",
        (CHANGES, SPENDS),
        "Propose having the planner agent break a goal into tasks (spawns a "
        "cloud agent). Use this instead of planning yourself.",
        {"goal": _GOAL},
        "server",
        False,
    ),
    HqAction(
        "post_note",
        "board",
        "Post a note",
        (CHANGES,),
        "Propose posting a short note from the user to this board. Agents read it.",
        {
            "text": {
                "type": "string",
                "description": "The note, in the user's words.",
                "minLength": 1,
                "maxLength": 2000,
            }
        },
        "server",
        True,
    ),
    HqAction(
        "diagram_artifact",
        "artifacts",
        "Diagram an artifact",
        (SPENDS,),
        "Propose having the diagram agent draw a diagram of an artifact's file "
        "(spawns a cloud agent).",
        {
            "artifact": _ARTIFACT,
            # A bare enum (no "type"): node-llama-cpp's grammar takes it as is.
            "style": {
                "enum": ["mermaid", "ascii", "plantuml", None],
                "description": "Diagram style, or null for the default.",
            },
        },
        "studio",
        False,
    ),
    HqAction(
        "add_diagram_to_board",
        "artifacts",
        "Add a diagram to the board",
        (CHANGES,),
        "Propose posting an artifact's latest diagram to this board.",
        {"artifact": _ARTIFACT},
        "studio",
        False,
    ),
)

BY_NAME = {a.name: a for a in CATALOG}

DOMAINS = (("runs", "Runs"), ("board", "Board"), ("artifacts", "Artifacts"))

PRESETS = (
    (
        "run-control",
        "Run control",
        ("pause_run", "resume_run", "retry_run", "stop_run"),
    ),
    ("board", "Board note", ("post_note",)),
    ("start-work", "Start work", ("run_goal", "plan_goal")),
    ("diagrams", "Diagrams", ("diagram_artifact", "add_diagram_to_board")),
)


def default_available() -> list[str]:
    return [a.name for a in CATALOG if a.default_available]


def normalize_names(names: Iterable[str] | None) -> list[str]:
    """Catalog names only, in catalog order, without duplicates."""
    wanted = {n for n in (names or ()) if isinstance(n, str)}
    return [a.name for a in CATALOG if a.name in wanted]


def effective_actions(
    requested: Iterable[str] | None, available: Iterable[str]
) -> list[str]:
    """What one question may use: requested ∩ available ∩ catalog.

    More than MAX_ENABLED requested raises TooManyActions (the route answers
    400) — counted before filtering, so the cap cannot be dodged by padding.
    """
    req = [n for n in (requested or ()) if isinstance(n, str)]
    if len(set(req)) > MAX_ENABLED:
        raise TooManyActions(f"at most {MAX_ENABLED} actions per question")
    allowed = set(normalize_names(available))
    return [n for n in normalize_names(req) if n in allowed]


def tool_spec(name: str) -> dict:
    """The function definition the model is offered for one action."""
    a = BY_NAME[name]
    return {
        "name": a.name,
        "description": a.description,
        "parameters": {
            "type": "object",
            "properties": a.params,
            "required": list(a.params),
        },
    }


def tool_specs(names: Iterable[str]) -> list[dict]:
    return [tool_spec(n) for n in normalize_names(names)]


def schema_tokens(name: str) -> int:
    """chars/4 of the function definition — what offering it costs the model
    (the same heuristic as the context packet, for the composer's one meter)."""
    return len(json.dumps(tool_spec(name))) // 4


def validate_args(name: str, args: object) -> tuple[dict | None, str | None]:
    """Check a proposal's args against the action's params: ``(clean, None)``
    or ``(None, reason)``. Unknown keys are dropped, never forwarded."""
    if not isinstance(args, dict):
        return None, "arguments must be an object"
    clean: dict = {}
    for key, spec in BY_NAME[name].params.items():
        if key not in args:
            return None, f"missing '{key}'"
        value = args[key]
        if "enum" in spec:
            if isinstance(value, str):
                value = value.strip() or None
            if value not in spec["enum"]:
                return None, f"'{key}' must be one of {[e for e in spec['enum'] if e]}"
            clean[key] = value
            continue
        types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
        if value is None:
            if "null" not in types:
                return None, f"'{key}' is required"
        elif not isinstance(value, str) or "string" not in types:
            return None, f"'{key}' must be text"
        else:
            value = value.strip()
            if not value:
                if "null" not in types:
                    return None, f"'{key}' is empty"
                value = None
            elif len(value) > spec.get("maxLength", 500):
                return None, f"'{key}' is too long"
        clean[key] = value
    return clean, None


def catalog_payload(available: Iterable[str]) -> dict:
    """``GET /hq/actions``: the catalog with each action's availability."""
    allowed = set(normalize_names(available))
    return {
        "max_enabled": MAX_ENABLED,
        "domains": [{"id": d, "label": label} for d, label in DOMAINS],
        "presets": [
            {"id": p, "label": label, "actions": list(names)}
            for p, label, names in PRESETS
        ],
        "actions": [
            {
                "name": a.name,
                "domain": a.domain,
                "label": a.label,
                "risk": list(a.risk),
                "description": a.description,
                "runs_on": a.runs_on,
                "available": a.name in allowed,
                "default_available": a.default_available,
                "schema_tokens": schema_tokens(a.name),
            }
            for a in CATALOG
        ],
    }
