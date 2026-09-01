"""Flow-level app-settings resolution, in a home both the supervisor and the CLI can reach.

``resolve_compiled_flows``/``is_compiled_flow`` started life inside
``supervisor/compiled_flow.py`` (their only caller at the time). The ``pathly-*`` CLI
shortcuts now need the same answer — "is this flow driven by the compiled executor?" — to
explain a run that has no ``STATE.json`` (see ``cli/_compiled.py``). Importing
``supervisor.compiled_flow`` from ``cli/`` to get it would drag the whole supervisor
package (orchestrator, terminal, spawn policy) into a small read-only shortcut, so the
resolution lives here instead: a top-level hub module that imports only from ``db/``,
in the same spirit as ``eventlog.py``/``fsm_http_client.py``.

``supervisor.compiled_flow`` re-exports both names, so its own callers and tests are
unchanged.
"""

from __future__ import annotations

SETTING_KEY = "flow.compiled_executors"


def resolve_compiled_flows() -> frozenset[str]:
    """Flow names that run via ``supervisor.compiled_flow.run_compiled_flow`` instead of
    the FSM engine.

    Reads the ``flow.compiled_executors`` app-setting (comma-separated flow names).
    Absent/unreadable -> empty (fail-open to the existing FSM path), the same contract
    ``command_gate``/``cost_cap``/``task_retry``'s own settings have.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), SETTING_KEY, None)
    except Exception:
        return frozenset()
    if not raw:
        return frozenset()
    return frozenset(name.strip() for name in raw.split(",") if name.strip())


def is_compiled_flow(flow_name: str) -> bool:
    return flow_name in resolve_compiled_flows()
