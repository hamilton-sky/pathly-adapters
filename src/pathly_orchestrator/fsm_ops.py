"""Pathly FSM state transitions — transport-independent."""

from __future__ import annotations

import datetime
import subprocess
from importlib.resources import files
from pathlib import Path

import yaml

from pathly_orchestrator.fsm import (
    evaluate_transition_rules,
    recover_state,
    route_feedback,
    run_gates,
    run_transition_actions,
)
from pathly_orchestrator.storage_paths import _safe_topic
from pathly_orchestrator.fsm_compose import (
    _SCHEMA_VERSION,
    _agent_hint,
    _blocked_response,
    _codex_subagent_hint,
    _resolve_adapter,
    _response_envelope,
    build_menu_payload,
    build_prompt,
    build_prompt_for_agent,
)


def _load_flow(flow_name: str, project_root: str | None = None) -> dict:
    if project_root is not None:
        try:
            import json as _json
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.flow_defs import (
                _assemble_flow_dict,
                read_flow_definitions,
                read_flow_nodes,
            )

            conn = get_db(project_root)
            for search_root in [project_root, None]:
                for row in read_flow_definitions(conn, search_root):
                    if row["name"] == flow_name:
                        node_rows = read_flow_nodes(conn, row["id"])
                        if node_rows:
                            flow_level_config = _json.loads(
                                row.get("config_json") or "{}"
                            )
                            return _assemble_flow_dict(
                                conn, row["id"], flow_level_config
                            )
                        return yaml.safe_load(row["flow_yaml"])
        except Exception:
            pass
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow_name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _resolve_storage_path(
    flow_config: dict | None, project_root: str, topic: str
) -> Path:
    topic = _safe_topic(topic)
    root = Path(project_root)
    for candidate in (
        root / "pathly" / "features" / topic,
        root / "pathly" / topic,
    ):
        if candidate.is_dir():
            return candidate
    # None exists — fall through to the flow's template default. Team pipeline → pathly/features/
    # <topic>; a goal decompose (consultation) uses a scope-nested topic (features/<f>/goals/<slug>
    # or project/goals/<slug>) which the pathly/<topic> candidate above resolves; debug/explore keep
    # their own subdir templates. Both legacy FEATURE (pathly/plans/<topic>) and flat GOAL
    # (pathly/goals/<topic>) candidates were removed once features + goals nest by scope.
    #
    # flow_config may be None: flow-less callers (telemetry, health, runner streams, /runner/event,
    # the otel CLI) only need "where does feature <topic> live" — not a flow template — so they get
    # the canonical flat home. The default MUST match team.flow.yaml's storage_path
    # (pathly/features/{topic}/) so a not-yet-created feature never resolves to legacy pathly/plans.
    template = (flow_config or {}).get("storage_path") or "pathly/features/{topic}/"
    return root / template.format(topic=topic)


def _get_head_sha(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def next_action(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]
    goal_id = args.get("goal_id") or ""

    flow_config = _load_flow(flow_name, project_root)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    from pathly_orchestrator import eventlog as _eventlog_pre

    _db_state = _eventlog_pre.read_state(str(storage_path))

    try:
        state_info = recover_state(storage_path, flow_config, state_doc=_db_state)
    except Exception as e:
        return {
            "schema_version": _SCHEMA_VERSION,
            "decision": "escalate",
            "current_state": "UNKNOWN",
            "conv": 0,
            "role": "human",
            "agent": "human",
            "agent_hint": {
                "agent": "human",
                "role": "human",
                "mode": "escalate",
                "instructions": "FSM state is corrupt or unreadable. Human intervention required.",
            },
            "stage_brief": {
                "state": "UNKNOWN",
                "conv": 0,
                "retry_count": 0,
                "open_feedback": [],
                "feedback_age_hours": None,
                "recent_events": [],
                "recent_consult": None,
                "plan_path": "",
            },
            "warnings": [{"code": "corrupt_state", "message": str(e)}],
            "blocked": True,
            "target_agent": "human",
            "file": "HUMAN_QUESTIONS.md",
            "instructions": f"FSM state recovery failed: {e}",
            "storage_path": str(storage_path),
        }

    from pathly_orchestrator import eventlog as _eventlog

    prior_state: dict = _eventlog.read_state(str(storage_path)) or {}

    stamped_state = dict(prior_state)
    needs_write = False

    if not prior_state.get("conv_start_sha"):
        stamped_state["conv_start_sha"] = _get_head_sha(project_root)
        needs_write = True

    if state_info["current_state"] == "BUILDING" and not prior_state.get(
        "build_baseline"
    ):
        try:
            dirty_run = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            dirty_paths = (
                sorted(
                    set(
                        line[3:].strip()
                        for line in dirty_run.stdout.splitlines()
                        if line.strip()
                    )
                )
                if dirty_run.returncode == 0
                else []
            )
        except Exception:
            dirty_paths = []
        truncated = len(dirty_paths) > 500
        if truncated:
            dirty_paths = dirty_paths[:500]
        baseline: dict = {
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "preexisting_dirty": dirty_paths,
        }
        if truncated:
            baseline["truncated"] = True
        stamped_state["build_baseline"] = baseline
        needs_write = True

    if needs_write:
        from pathly_orchestrator import eventlog as _elog_ws

        _elog_ws.write_state(
            str(storage_path),
            {**stamped_state, "current": state_info["current_state"]},
            flow_config,
        )
        prior_state = stamped_state

    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.stage_configs import (
            read_stage_config as _read_stage_cfg,
        )

        _cfg_conn = _get_db()
        _stage_cfg = _read_stage_cfg(
            _cfg_conn, project_root, topic, state_info["current_state"]
        )
        if _stage_cfg:
            if _stage_cfg.get("agent"):
                flow_config = dict(flow_config)
                flow_config["agent_map"] = dict(flow_config.get("agent_map", {}))
                flow_config["agent_map"][state_info["current_state"]] = _stage_cfg[
                    "agent"
                ]
            if _stage_cfg.get("adapter"):
                flow_config["adapter_map"] = dict(flow_config.get("adapter_map", {}))
                flow_config["adapter_map"][state_info["current_state"]] = _stage_cfg[
                    "adapter"
                ]
    except Exception:
        pass

    feedback = route_feedback(flow_config, storage_path)

    if feedback is not None:
        result = _blocked_response(
            feedback,
            state_info,
            storage_path,
            preferred_adapter=_resolve_adapter(
                flow_config, state_info["current_state"]
            ),
        )
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(
                    feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _agent_hint(
                    feedback["target_agent"], instructions
                )
                result["codex_subagent"] = _codex_subagent_hint(
                    feedback["target_agent"], instructions
                )
            except Exception:
                result["instructions"] = None
        return result

    if state_info["current_state"] == "DONE":
        return {"done": True}

    instructions = build_prompt(
        flow_config, state_info["current_state"], storage_path, goal_id
    )
    agent = flow_config["agent_map"][state_info["current_state"]]
    menu = build_menu_payload(flow_config, state_info["current_state"], storage_path)
    result = _response_envelope(
        state_info=state_info,
        storage_path=storage_path,
        agent=agent,
        instructions=instructions,
        menu=menu,
        preferred_adapter=_resolve_adapter(flow_config, state_info["current_state"]),
        flow=flow_config,
    )
    result["limits"] = state_info["limits"]
    return result


# Lazy re-export of complete_stage to break the fsm_ops <-> fsm_ops_complete
# import cycle. fsm_ops_complete imports ~12 helpers from this module at load time;
# a top-level `from fsm_ops_complete import complete_stage` here would force that
# module to load while fsm_ops is still initializing — which raises ImportError
# whenever fsm_ops_complete is imported first. PEP 562 module __getattr__ defers
# the import to first attribute access, so `from ...fsm_ops import complete_stage`
# still resolves for every call site, in any import order.
def __getattr__(name):
    if name == "complete_stage":
        from pathly_orchestrator.fsm_ops_complete import complete_stage

        return complete_stage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
