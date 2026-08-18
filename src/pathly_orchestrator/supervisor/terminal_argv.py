"""Which argv this spawn runs, and the precondition for interactive mode.

Separated from the spawn because it is the seam a NEW ADAPTER touches: adding an engine
changes how argv is built, and should not require opening the process-lifecycle code.
"""

from __future__ import annotations

from typing import Callable, Optional

from .state import RunnerState


def _resolve_spawn_argv(
    state: RunnerState,
    instructions: str,
    adapter: str,
    model: str,
    session: Optional[str],
    autonomy: bool,
    early_advance: bool,
    broadcast_fn: Optional[Callable],
) -> list:
    """Build the argv for this spawn.

    Interactive mode depends on early-advance to notice the agent is done, so without it the
    run would hang rather than misbehave — hence the hard precondition, broadcast to the UI
    before it raises so the operator sees WHY rather than a bare traceback.
    """
    from pathly_orchestrator.runner import resolve_argv, resolve_interactive_argv

    if state.interactive and not early_advance:
        msg = "Interactive mode requires PATHLY_RUNNER_EARLY_ADVANCE=1"
        if broadcast_fn:
            try:
                broadcast_fn(state.topic, {"type": "RUNNER_WARNING", "message": msg})
            except Exception:
                pass
        raise RuntimeError(msg)

    if state.interactive:
        return resolve_interactive_argv(
            adapter, model, session=session, autonomy=autonomy
        )
    return resolve_argv(
        adapter,
        instructions,
        model,
        session=session,
        autonomy=autonomy,
        interactive=False,
    )
