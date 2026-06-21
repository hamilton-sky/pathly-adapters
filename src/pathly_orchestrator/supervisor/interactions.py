"""Agent question surfacing and user-answer waiting."""

from __future__ import annotations

import time
from typing import Callable, Optional

from .state import RunnerState, logger
from .registry import _lock


def _await_agent_question(
    state: RunnerState,
    topic: str,
    ask_q: dict,
    broadcast_fn: Optional[Callable],
) -> Optional[str]:
    """Surface a denied AskUserQuestion to the user via SSE and wait for their answer.
    Returns the answer string, or None if the run was aborted.
    """
    tool_input = ask_q.get("tool_input") or {}
    questions = tool_input.get("questions") or []
    if not questions:
        return None
    first_q = questions[0]
    question_text = first_q.get("question", "")
    options = first_q.get("options") or []

    with _lock:
        state._awaiting_agent_answer = True
        state._agent_question_answer = None
        state._agent_question_event.clear()

    if broadcast_fn:
        try:
            broadcast_fn(
                topic,
                {
                    "type": "AGENT_QUESTION",
                    "topic": topic,
                    "question": question_text,
                    "options": options,
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)

    # Wait for user answer or abort
    while True:
        with _lock:
            if state._abort_flag:
                state._awaiting_agent_answer = False
                return None
            answer = state._agent_question_answer
        if answer is not None:
            break
        time.sleep(0.05)

    with _lock:
        state._awaiting_agent_answer = False
        state._agent_question_answer = None

    return answer
