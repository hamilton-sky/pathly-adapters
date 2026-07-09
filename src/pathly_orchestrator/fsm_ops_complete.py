"""FSM complete_stage implementation — imported by fsm_ops (bottom-of-file)."""

from __future__ import annotations

# Module reference — attribute access happens at CALL time so monkeypatching
# fsm_ops._load_flow / fsm_ops.build_prompt in tests still works.
import pathly_orchestrator.fsm_ops as _fops

from pathly_orchestrator.fsm import (
    append_event,
    evaluate_transition_rules,
    recover_state,
    route_feedback,
    run_gates,
    run_transition_actions,
)


def complete_stage(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]
    decision: str | None = args.get("decision")
    resolved_files: list[str] | None = args.get("resolved_files")

    flow_config = _fops._load_flow(flow_name, project_root)
    storage_path = _fops._resolve_storage_path(flow_config, project_root, topic)

    board = args.get("board", "feature")
    scope = args.get("scope") or topic
    goal_id = args.get("goal_id")

    if resolved_files:
        feedback_dir = storage_path / "feedback"
        for filename in resolved_files:
            target = feedback_dir / filename
            if target.exists():
                target.unlink()
                append_event(
                    storage_path, {"type": "FEEDBACK_RESOLVED", "file": filename}
                )

    from pathly_orchestrator import eventlog as _eventlog

    state_before: dict | None = _eventlog.read_state(str(storage_path))

    try:
        state_info = recover_state(storage_path, flow_config, state_doc=state_before)
    except Exception as e:
        return {
            "schema_version": _fops._SCHEMA_VERSION,
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

    feedback = route_feedback(flow_config, storage_path)
    if feedback is not None:
        result = _fops._blocked_response(
            feedback,
            state_info,
            storage_path,
            preferred_adapter=_fops._resolve_adapter(
                flow_config, state_info["current_state"]
            ),
        )
        if feedback["target_agent"] != "human":
            try:
                instructions = _fops.build_prompt_for_agent(
                    feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _fops._agent_hint(
                    feedback["target_agent"], instructions
                )
                result["codex_subagent"] = _fops._codex_subagent_hint(
                    feedback["target_agent"], instructions
                )
            except Exception:
                result["instructions"] = None
        return result

    if state_info["current_state"] == "DONE":
        return {"done": True}

    eval_result: str | dict = evaluate_transition_rules(
        flow_config,
        state_info["current_state"],
        storage_path,
        goal_id=goal_id,
        feature_scope=scope,
    )

    if isinstance(eval_result, dict) and eval_result.get("decide") is True:
        if decision is None:
            context_file = eval_result.get("context_file", "")
            context_contents: str | None = None
            if context_file:
                ctx_path = storage_path / context_file
                if ctx_path.exists():
                    try:
                        context_contents = ctx_path.read_text(encoding="utf-8")
                    except OSError:
                        context_contents = None
            return {
                "decide": True,
                "question": eval_result["question"],
                "context": context_contents,
                "options": eval_result["options"],
                "default": eval_result["default"],
            }
        else:
            options = eval_result["options"]
            default = eval_result["default"]
            if decision not in options:
                decision = default
            next_state = options.get(decision, options.get(default, ""))
            append_event(
                storage_path,
                {
                    "type": "DECIDE_ROUTING",
                    "chosen": next_state,
                    "decision_input": decision,
                    "options": options,
                },
            )
    else:
        if not isinstance(eval_result, str):
            raise RuntimeError(
                f"evaluate_transition_rules returned unexpected type {type(eval_result)!r}; "
                f"expected str or decide-dict"
            )
        next_state = eval_result

    gate_failure = run_gates(
        flow_config,
        state_info["current_state"],
        next_state,
        storage_path,
        topic,
        state_info["conv"],
        goal_id=goal_id,
        feature_scope=scope,
        board=board,
    )
    if gate_failure is not None:
        feedback = route_feedback(flow_config, storage_path)
        if feedback is None:
            feedback = {
                "target_agent": "human",
                "file": gate_failure.get("feedback_file", "HUMAN_QUESTIONS.md"),
            }
        result = _fops._blocked_response(
            feedback,
            state_info,
            storage_path,
            preferred_adapter=_fops._resolve_adapter(
                flow_config, state_info["current_state"]
            ),
        )
        if feedback["target_agent"] != "human":
            try:
                instructions = _fops.build_prompt_for_agent(
                    feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _fops._agent_hint(
                    feedback["target_agent"], instructions
                )
                result["codex_subagent"] = _fops._codex_subagent_hint(
                    feedback["target_agent"], instructions
                )
            except Exception:
                result["instructions"] = None
        return result

    run_transition_actions(
        flow_config,
        state_info["current_state"],
        next_state,
        storage_path,
        topic,
        state_info["conv"],
        # Pass the REAL repo root — never re-derive it by walking storage_path up by template
        # depth, which lands on the feature dir for multi-segment board-scoped topics and nests
        # pathly/pipeline-walkthrough/ inside the feature folder.
        project_root=project_root or None,
    )

    from pathly_orchestrator import eventlog as _elog_ws

    prior_state = _elog_ws.read_state(str(storage_path)) or dict(state_before or {})
    prior_state.pop("conv_start_sha", None)
    prior_state.pop("build_baseline", None)
    _elog_ws.write_state(
        str(storage_path), {**prior_state, "current": next_state}, flow_config
    )

    append_event(
        storage_path,
        {
            "type": "STATE_TRANSITION",
            "from": state_info["current_state"],
            "to": next_state,
        },
        flow=flow_config,
    )

    if next_state == "DONE":
        return {"done": True}

    instructions = _fops.build_prompt(
        flow_config, next_state, storage_path, goal_id or ""
    )
    agent = flow_config["agent_map"][next_state]
    menu = _fops.build_menu_payload(flow_config, next_state, storage_path)
    result = _fops._response_envelope(
        state_info=state_info,
        storage_path=storage_path,
        agent=agent,
        instructions=instructions,
        menu=menu,
        current_state_value=next_state,
        preferred_adapter=_fops._resolve_adapter(flow_config, next_state),
        flow=flow_config,
    )
    result["limits"] = state_info["limits"]
    result["next_state"] = next_state
    try:
        from pathly_orchestrator.supervisor.artifact_reconcile import (
            reconcile_artifacts,
        )

        reconcile_artifacts(storage_path, scope, goal_id=goal_id, board=board)
    except Exception:
        pass  # best-effort; the ledger + files remain authoritative
    return result
