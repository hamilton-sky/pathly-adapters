"""The prompt a DAG task agent runs — assembled in ONE place (fsm-fan-out Phase E).

``scheduler._worker`` used to build this inline: compose ``development/execute-task``,
append the runner contract, append the retry ladder, append board context. What it never
did is **substitute the fragment placeholders**, and that is the bug this module exists to
close.

``compose_skill`` returns a body whose fragments still carry literal ``<fsm_feature>``,
``<feature_path>``, ``<feature>``, ``<board>`` and ``<run_category>`` markers — the FSM path
fills them in ``fsm_compose.build_prompt`` and the board path in
``board_run._inject_board_prompt_vars``, but the DAG path had no injector at all. So a loop
task agent was handed a ``completion-report`` fragment telling it to write its ``AGENT_DONE``
under the literal string ``<fsm_feature>``: the event is mis-keyed, its projected invocation
never lands on the run, and the task shows up unbilled and absent from the Monitor. Exactly
the failure the root ``CLAUDE.md`` documents for board runs ("a missing ``completion-report``
no longer means vanished + unbilled") — the DAG path was the remaining hole.

It was survivable while ``executor: loop`` owned its own telemetry: a task that wrote NO
usable ``AGENT_DONE`` got a synthetic one from
``terminal_reconcile._synthesize_agent_done_if_missing``, stamped ``category="loop"``. Under
Phase E these tasks run inside an FSM stage, where ``executor_owned_telemetry`` is False and
that safety net does not fire — so the substitution has to be real.

``run_category`` is ``"loop"`` rather than the FSM default ``"flow"``: a DAG task IS a loop
task however it was reached, and the Monitor's RECENT list buckets on that stamp.
"""

from __future__ import annotations

import logging
from typing import Optional

from . import task_retry as _task_retry
from ..fsm_compose import RUNNER_CONTRACT_BLOCK

logger = logging.getLogger("pathly.task_prompt")

# The Pathly role a DAG task agent occupies. Stamped explicitly because a loop task agent
# otherwise has no role, and fragments that ask for one (notably code-query's `role` field)
# silently gate an unknown role to a thin tier.
_TASK_ROLE = "builder"

_TASK_SKILL = "development/execute-task"


def _inject_vars(body: str, state, board: str, scope: str, agent_role: str) -> str:
    """Fill the fragment placeholders ``compose_skill`` leaves literal. Never raises.

    Reuses ``fsm_compose._inject_prompt_vars`` — the SAME injector the FSM and board paths
    call — so the three prompt-assembly paths can never drift on what a placeholder means.
    On any failure the composed body is returned unchanged: an un-substituted prompt still
    runs the task, and losing the task to an injector hiccup would be worse.
    """
    try:
        from pathlib import Path

        from pathly_orchestrator.fsm_compose import _inject_prompt_vars
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        project_root = getattr(state, "project_root", "") or ""
        raw = getattr(state, "storage_path", "") or _resolve_storage_path(
            None, project_root, getattr(state, "topic", "") or scope
        )
        return _inject_prompt_vars(
            body,
            feature=scope,
            project_root=project_root,
            agent_role=agent_role,
            storage_path=Path(str(raw)) if raw else None,
            skill=_TASK_SKILL,
            board_tier=(
                board if board in ("feature", "project", "global") else "feature"
            ),
            # A DAG task is a LOOP task, whether it was reached through executor: loop or
            # through an FSM fan-out state — the Monitor buckets RECENT runs on this stamp.
            run_category="loop",
        )
    except Exception:
        logger.debug("task_prompt: placeholder injection failed", exc_info=True)
        return body


def build_task_prompt(
    task: dict,
    state,
    board: str,
    scope: str,
    *,
    adapter: str,
    task_id: str,
) -> str:
    """The full prompt for one DAG task.

    Layered in a fixed order, each layer best-effort so a missing one never costs the task:

    1. the composed ``development/execute-task`` body (progress logging, comms-post,
       completion-report) with its placeholders substituted — falling back to the raw task
       text when composition is unavailable;
    2. the runner contract, so a task agent never tries to advance the FSM itself;
    3. the retry ladder, from the second attempt on;
    4. the scope-aware board context.

    The runner contract is appended AFTER the compose try/except deliberately: the raw-text
    fallback is the path where the agent has the LEAST guidance, so it must not be the one
    path that loses the contract.
    """
    task_text = task.get("text", "") or ""

    try:
        from pathly_orchestrator.skills.compose import compose_skill

        body = _inject_vars(
            compose_skill(_TASK_SKILL, adapter or "claude"),
            state,
            board,
            scope,
            _TASK_ROLE,
        )
        instructions = (
            f"{body}\n\n## Your task\n\n"
            f"(Your Pathly role for this task is **{_TASK_ROLE}** — use it wherever a "
            "fragment asks for your role, e.g. the code-query `role` field.)\n\n"
            f"{task_text}"
        )
    except Exception:
        instructions = task_text

    instructions += f"\n\n{RUNNER_CONTRACT_BLOCK}"
    instructions += _task_retry.build_retry_context(task)

    # The same scope-aware board context (governance + memory, honoring the Reads toggle)
    # the FSM/team path gets, so a task agent isn't blind to the board.
    try:
        from pathly_orchestrator.runner.comms_context import board_context_for

        ctx: Optional[str] = board_context_for(
            board,
            scope,
            getattr(state, "project_root", "") or "",
            task_text,
            task_id=task_id,
        )
        if ctx:
            instructions = f"{instructions}\n\n{ctx}"
    except Exception:
        pass

    return instructions
