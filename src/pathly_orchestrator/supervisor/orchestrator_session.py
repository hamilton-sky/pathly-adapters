"""Session continuity for the next FSM stage — lifted out of ``orchestrator._loop``.

Same-adapter consecutive stages share a CLI session so the next stage does not re-read the
context the previous one already paid for; a cross-adapter transition, or an adapter with no
``--resume``, opens a new one, and so does a reviewer stage (``INDEPENDENT_ROLES``), which must
not inherit the builder's transcript. That decision was ~35 lines inline in ``_loop``; it is one
self-contained question with one answer, so it lives here (SOLID rule #1) and — since
``orchestrator.py`` is frozen by the size ratchet and may only shrink — extracting it is what
paid for the fan-out call sites ``_loop`` gained in Phase C.

Behaviour is unchanged: the same reuse predicate, the same ``degraded`` flag, the same
``SESSION`` event on the same channel.
"""

from __future__ import annotations

from typing import Callable, Optional

from .state import RunnerState
from .registry import _lock

# Roles whose stage never resumes the previous stage's session. A resumed claude session
# restores the whole conversation, tool calls and results included, so a reviewer that
# resumed the builder's session would hold the builder's transcript whatever its prompt
# leaves out. The decision is made by role (``fsm_compose_tables.agent_role_of``), the same
# rule that gives the reviewer its Review packet.
INDEPENDENT_ROLES = frozenset({"reviewer"})


def resolve_session(
    state: RunnerState,
    topic: str,
    preferred_adapter: str,
    broadcast: Callable[[dict], None],
    stage_agent: str = "",
) -> tuple[Optional[str], bool, bool]:
    """Decide this stage's session and announce it.

    Returns ``(session_id, autonomy_for_adapter, adapter_supports_resume)``:

    * ``session_id`` — the open session to resume, or ``None`` to open a new one. Always
      ``None`` when *stage_agent* (the ``/next_action`` ``agent``, an ``agent_map`` entry
      such as ``team/review``) runs as one of ``INDEPENDENT_ROLES``.
    * ``autonomy_for_adapter`` — this adapter's autonomy setting, read under the lock at
      the same moment as the open session (they are read together in ``_loop`` and must
      stay a single consistent snapshot).
    * ``adapter_supports_resume`` — whether the adapter can resume at all; ``_loop`` stores
      it on the ``OpenSession`` it writes after the stage returns.

    Emits the ``SESSION`` event (``kind`` = continued/opened, plus ``degraded`` when the
    adapter cannot resume) through the caller's broadcast helper.
    """
    from pathly_orchestrator.adapters import resolve_command
    from pathly_orchestrator.fsm_compose_tables import agent_role_of

    independent = agent_role_of(stage_agent) in INDEPENDENT_ROLES

    with _lock:
        open_sess = state.open_session
        autonomy_for_adapter = state.autonomy.get(preferred_adapter, True)

    session_id: Optional[str] = None
    degraded = False

    try:
        cmd_info = resolve_command(preferred_adapter, "", "", autonomy=False)
        adapter_supports_resume = cmd_info["supports_resume"]
    except ValueError:
        adapter_supports_resume = False

    if (
        not independent
        and open_sess is not None
        and open_sess.adapter == preferred_adapter
        and adapter_supports_resume
        and open_sess.session_id
    ):
        session_id = open_sess.session_id
        session_action = "continued"
    else:
        session_id = None
        session_action = "opened"
        if not adapter_supports_resume:
            degraded = True

    broadcast(
        {
            "type": "SESSION",
            "topic": topic,
            "adapter": preferred_adapter,
            "kind": session_action,
            "degraded": degraded,
            "independent": independent,
        }
    )
    return session_id, autonomy_for_adapter, adapter_supports_resume
