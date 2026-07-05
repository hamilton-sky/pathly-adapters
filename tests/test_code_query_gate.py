"""Unit tests for the /code/query role gate (_gate).

The gate must let Pathly's HEADLESS agents through. The FSM/loop emit host-neutral
roles ('worker'/'explorer'), and a loop task agent may not name a role at all — so an
unrecognized/empty role must degrade to a usable, board-LOGGED tier, NOT a silent
'disabled' no-op. Silent-off was the reason code-query never fired in loop runs even
when the agent called it. Explicitly-excluded roles stay denied.
"""

from pathly_orchestrator.http_server.blueprints.code.query import _gate


def test_worker_role_gets_full_tier():
    # 'worker' is the FSM/loop host-neutral role for implementation work -> full access.
    assert _gate("worker", "callers") is None
    assert _gate("worker", "impact") is None
    assert _gate("worker", "symbol") is None


def test_empty_role_degrades_to_lookup_not_disabled():
    # A loop task agent that never named its role still gets basic code-query.
    assert _gate("", "symbol") is None
    assert _gate("", "context") is None
    # ...but not the full-tier ops (degraded, not full).
    assert _gate("", "impact") == "op-not-permitted"


def test_unknown_role_degrades_to_lookup():
    assert _gate("some-unmapped-role", "symbol") is None
    assert _gate("some-unmapped-role", "callers") == "op-not-permitted"


def test_excluded_roles_stay_disabled():
    for r in ("web-researcher", "orchestrator", "evaluator", "human"):
        assert _gate(r, "symbol") == "disabled", r


def test_known_roles_unchanged():
    assert _gate("builder", "impact") is None
    assert _gate("explorer", "callers") is None
    assert _gate("tester", "chain") is None
    assert _gate("tester", "impact") == "op-not-permitted"
    assert _gate("quick", "symbol") is None
    assert _gate("quick", "impact") == "op-not-permitted"
