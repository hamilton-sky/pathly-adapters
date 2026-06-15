"""Tests for start_board_run and POST /comms/run (BOARD-RUNTIME-SPEC §2/US4).

Verifies:
- start_board_run with a fake spawn_fn returns ok=True and calls the spawn.
- The prompt passed to spawn_fn contains the board context.
- The board lock is released after the call (is_locked returns False).
- A second concurrent start_board_run while a blocking fake holds the lock
  returns ok=False / error=board_busy.
- POST /comms/run on a busy board returns 409.
"""
from __future__ import annotations

import json
import threading

import pytest

from pathly_orchestrator.supervisor import board_lock


@pytest.fixture(autouse=True)
def _clear_lock():
    """Ensure no board locks leak between tests."""
    board_lock._held.clear()
    yield
    board_lock._held.clear()


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Prevent embed_async from spawning daemon threads that race the test DB."""
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_msg(client, *, msg_type: str, text: str, board: str = "feature",
              scope: str = "f1") -> str:
    r = client.post("/comms/post", json={
        "feature": scope,
        "from": "human",
        "type": msg_type,
        "text": text,
        "board": board,
        "scope": scope,
    })
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _make_fake_spawn(*, calls: list, return_value: dict | None = None, block_event=None):
    """Return a fake spawn_fn that records its keyword arguments.

    If block_event is given the fake waits for it before returning — this
    simulates a long-running spawn so a concurrent caller sees a locked board.
    """
    if return_value is None:
        return_value = {"result": "ok"}

    def fake(**kwargs):
        calls.append(kwargs)
        if block_event is not None:
            block_event.wait()
        return return_value

    return fake


# ---------------------------------------------------------------------------
# Tests — start_board_run
# ---------------------------------------------------------------------------

def test_start_board_run_ok_and_lock_released(client):
    """start_board_run returns ok=True; board lock is released when done."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    # Post a decision so the board context is non-empty.
    _post_msg(client, msg_type="decision", text="Use Python 3.11")

    calls: list = []
    fake = _make_fake_spawn(calls=calls)

    result = start_board_run(
        "feature", "f1", "single-agent",
        instructions="Analyse the board",
        spawn_fn=fake,
        block=True,
    )

    assert result["ok"] is True
    assert result["mode"] == "single-agent"
    assert "run_id" in result

    # The fake was called exactly once.
    assert len(calls) == 1
    spawned_prompt = calls[0]["prompt"]
    # Prompt must contain the board context (the decision text).
    assert "Use Python 3.11" in spawned_prompt
    # Instructions are prepended.
    assert "Analyse the board" in spawned_prompt

    # Lock is released after the call.
    assert not board_lock.is_locked("feature", "f1")


def test_start_board_run_board_busy_returns_error():
    """A second start_board_run while the first holds the lock returns board_busy."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    blocker = threading.Event()
    first_started = threading.Event()
    calls_first: list = []
    calls_second: list = []

    def blocking_spawn(**kwargs):
        calls_first.append(kwargs)
        first_started.set()
        blocker.wait()
        return {"result": "ok"}

    result_holder: dict = {}

    def run_first():
        r = start_board_run("feature", "f1", "single-agent", spawn_fn=blocking_spawn)
        result_holder["first"] = r

    t = threading.Thread(target=run_first, daemon=True)
    t.start()

    # Wait for the first run to acquire the lock before attempting the second.
    first_started.wait(timeout=5)

    fake2 = _make_fake_spawn(calls=calls_second)
    result_holder["second"] = start_board_run("feature", "f1", "single-agent", spawn_fn=fake2)

    # Let the first run finish.
    blocker.set()
    t.join(timeout=5)

    # Second call must have been rejected.
    assert result_holder["second"]["ok"] is False
    assert result_holder["second"]["error"] == "board_busy"
    # Second fake was never called.
    assert calls_second == []

    # After first finishes, lock is released.
    assert not board_lock.is_locked("feature", "f1")


def test_start_board_run_lock_released_on_spawn_exception():
    """Even if spawn_fn raises, the board lock must be released."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    def boom(**kwargs):
        raise RuntimeError("spawn failed")

    with pytest.raises(RuntimeError):
        start_board_run("feature", "f1", "single-agent", spawn_fn=boom, block=True)

    assert not board_lock.is_locked("feature", "f1")


# ---------------------------------------------------------------------------
# Tests — POST /comms/run
# ---------------------------------------------------------------------------

def test_comms_run_busy_board_returns_409(client, monkeypatch):
    """POST /comms/run on a locked board returns 409."""
    from pathly_orchestrator.supervisor.board_run import start_board_run
    import pathly_orchestrator.supervisor.board_run as _br

    # Manually lock the board to simulate a running agent.
    board_lock.acquire("feature", "f1", "some-existing-run-id")

    # Stub start_board_run so it uses the real lock but a fake spawn.
    original = _br.start_board_run

    def _patched(board, scope, mode, instructions="", *, project_root="", **kw):
        calls: list = []
        return original(
            board, scope, mode, instructions,
            project_root=project_root,
            spawn_fn=_make_fake_spawn(calls=calls),
        )

    monkeypatch.setattr(_br, "start_board_run", _patched)

    r = client.post("/comms/run", json={
        "board": "feature",
        "scope": "f1",
        "mode": "single-agent",
    })
    assert r.status_code == 409
    payload = json.loads(r.data)
    assert payload["ok"] is False
    assert "board_busy" in payload["error"]


def test_comms_run_missing_scope_returns_400(client):
    """POST /comms/run without scope returns 400."""
    r = client.post("/comms/run", json={"board": "feature", "mode": "single-agent"})
    assert r.status_code == 400


def test_comms_run_ok(client, monkeypatch):
    """POST /comms/run with a fake spawn returns 200 with ok=True."""
    import pathly_orchestrator.supervisor.board_run as _br

    calls: list = []

    def fake_start(board, scope, mode, instructions="", *, project_root="", **kw):
        calls.append({"board": board, "scope": scope, "mode": mode})
        return {"ok": True, "run_id": "test-run-123", "mode": mode, "result": {"result": "ok"}}

    monkeypatch.setattr(_br, "start_board_run", fake_start)

    r = client.post("/comms/run", json={
        "board": "feature",
        "scope": "f1",
        "mode": "single-agent",
        "instructions": "Summarise the board",
    })
    assert r.status_code == 200
    payload = json.loads(r.data)
    assert payload["ok"] is True
    assert payload["run_id"] == "test-run-123"
    assert len(calls) == 1
    assert calls[0]["scope"] == "f1"


def test_default_spawn_calls_terminal_with_runnerstate(monkeypatch):
    """Regression: the REAL spawn path (spawn_fn=None) must call
    _run_stage_via_terminal with a RunnerState as the first positional arg and
    the (state, instructions, adapter, model, run_id, broadcast_fn) signature —
    the fake-spawn tests never exercise this, so it is guarded explicitly."""
    import pathly_orchestrator.supervisor.terminal as _term
    from pathly_orchestrator.supervisor import board_run
    from pathly_orchestrator.supervisor.state import RunnerState

    captured: dict = {}

    def fake_rsvt(state, instructions, adapter, model, run_id, broadcast_fn, *a, **k):
        captured["state"] = state
        captured["instructions"] = instructions
        captured["adapter"] = adapter
        captured["run_id"] = run_id
        return {"result": "ok"}

    monkeypatch.setattr(_term, "_run_stage_via_terminal", fake_rsvt)

    out = board_run.start_board_run(
        "feature", "wire", "single-agent", "do X",
        project_root="/tmp", spawn_fn=None, block=True,
    )
    assert out["ok"] is True
    assert isinstance(captured["state"], RunnerState)
    assert captured["state"].topic == "wire"
    assert captured["adapter"] == "claude"
    assert "do X" in captured["instructions"]
    assert board_lock.is_locked("feature", "wire") is False  # released


def test_lifecycle_callbacks_fire_in_order():
    """on_start fires before the spawn, on_done fires after with the result —
    this is how the board shows 'started…' then 'done — summary' (not blind)."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    events: list = []
    start_board_run(
        "feature", "lc", "single-agent", "x",
        spawn_fn=lambda **k: {"result": "did the thing"},
        on_start=lambda rid: events.append(("start", rid)),
        on_done=lambda rid, res: events.append(("done", res.get("result"))),
        block=True,
    )
    assert [e[0] for e in events] == ["start", "done"]
    assert events[1][1] == "did the thing"
    assert not board_lock.is_locked("feature", "lc")


def test_async_run_returns_started_immediately():
    """Without block=True the run is async: returns status='started' at once and
    holds the lock until the background spawn completes."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    release = threading.Event()
    started = threading.Event()

    def slow_spawn(**k):
        started.set()
        release.wait(timeout=5)
        return {"result": "ok"}

    out = start_board_run("feature", "async1", "single-agent", "x", spawn_fn=slow_spawn)
    assert out["ok"] is True and out.get("status") == "started"
    assert started.wait(timeout=5)               # background thread is running
    assert board_lock.is_locked("feature", "async1")  # still held mid-run
    release.set()
    # lock frees once the background thread finishes
    for _ in range(50):
        if not board_lock.is_locked("feature", "async1"):
            break
        import time as _t; _t.sleep(0.05)
    assert not board_lock.is_locked("feature", "async1")
