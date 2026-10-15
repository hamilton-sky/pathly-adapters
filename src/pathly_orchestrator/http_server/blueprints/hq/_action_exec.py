"""Execute a confirmed HQ operator action through the REAL endpoint (local-operator 02).

Every server-run action is a request to the same route a human click in Studio
makes (the mapping below), dispatched in-process. So the operator can never
take a path the UI can't: the same validation, refusal shapes (a busy board, a
cost ceiling), board posts and SSE broadcasts. No new business logic here —
only "which route, with which body", and reading its answer as one line.

| action      | route                                   |
|-------------|-----------------------------------------|
| pause_run   | POST /runs/<run_id>/pause               |
| resume_run  | POST /runs/<run_id>/resume              |
| retry_run   | POST /runs/<run_id>/retry               |
| stop_run    | POST /runs/<run_id>/stop                |
| run_goal    | POST /comms/goals/run                   |
| plan_goal   | POST /comms/goals/decompose (planner)   |
| post_note   | POST /comms/post (from: human, note)    |

``diagram_artifact`` / ``add_diagram_to_board`` run in Studio (its editor
diagram code); the server validates them and records their audit entry.
"""

from __future__ import annotations

from dataclasses import dataclass

# What RunControls' Retry sends (apiStartFlow's own defaults): RunDetail does
# not carry the original run's caps, and neither does HQ.
RETRY_MAX_ITERATIONS = 50
RETRY_MAX_COST_USD = 10.0


@dataclass
class Outcome:
    ok: bool
    summary: str
    status_code: int
    payload: dict


def route_for(name: str, args: dict, board: str, project_root: str | None):
    """``(method, path, body)`` of the endpoint that performs *name*."""
    root = project_root or ""
    if name in ("pause_run", "resume_run", "stop_run"):
        action = name.split("_")[0]
        return "POST", f"/runs/{args['run_id']}/{action}", {}
    if name == "retry_run":
        body = {
            "flow": args["flow"],
            "project_root": args.get("project_root") or root,
            "max_iterations": RETRY_MAX_ITERATIONS,
            "max_cost_usd": RETRY_MAX_COST_USD,
        }
        return "POST", f"/runs/{args['run_id']}/retry", body
    if name == "run_goal":
        return (
            "POST",
            "/comms/goals/run",
            {"goal_id": args["goal_id"], "project_root": root},
        )
    if name == "plan_goal":
        body = {"goal_id": args["goal_id"], "mode": "planner", "project_root": root}
        return "POST", "/comms/goals/decompose", body
    if name == "post_note":
        body = {
            "feature": board,
            "from": "human",
            "type": "note",
            "text": args["text"],
            "board": "feature",
            "scope": board,
        }
        return "POST", "/comms/post", body
    raise ValueError(f"'{name}' is not a server-run action")


def _call(method: str, path: str, body: dict) -> tuple[int, dict]:
    """Dispatch to the app's own route in-process (loopback, no browser
    Origin: the same trust the middleware gives Studio and local agents)."""
    from flask import current_app

    resp = current_app.test_client().open(path, method=method, json=body)
    data = resp.get_json(silent=True)
    return resp.status_code, data if isinstance(data, dict) else {}


def _succeeded(name: str, status: int, payload: dict) -> bool:
    if not 200 <= status < 300 or payload.get("ok") is False or payload.get("error"):
        return False
    if name == "stop_run":
        return bool(payload.get("stopped"))
    return True


def _reason(status: int, payload: dict) -> str:
    text = payload.get("error") or payload.get("reason") or f"HTTP {status}"
    return str(text).replace("_", " ")[:200]


_DONE = {
    "pause_run": "Paused",
    "resume_run": "Resumed",
    "retry_run": "Restarted",
    "stop_run": "Stopped",
    "run_goal": "Started",
    "plan_goal": "Planning",
    "post_note": "Posted",
}


def execute(
    name: str, args: dict, title: str, board: str, project_root: str | None
) -> Outcome:
    """Run a confirmed server action; never raises."""
    try:
        method, path, body = route_for(name, args, board, project_root)
        status, payload = _call(method, path, body)
    except Exception as exc:  # the card shows the failure; nothing retried
        return Outcome(False, f"Failed: {exc}"[:200], 500, {})
    if _succeeded(name, status, payload):
        target = title.split(" ", 1)[1] if " " in title else title
        extra = f" → new run {payload['run_id'][:12]}" if name == "retry_run" else ""
        return Outcome(True, f"{_DONE[name]} {target}{extra}", status, payload)
    return Outcome(False, f"Failed: {_reason(status, payload)}", status, payload)
