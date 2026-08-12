"""Unit tests for pathly_orchestrator.runner."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

import pathly_orchestrator.runner as runner_mod
from pathly_orchestrator.runner import (
    handle_blocked,
    handle_decide,
    invoke_agent,
    parse_result,
    resolve_argv,
    resolve_stage,
    run_flow,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_NEXT_ACTION_PATH = "pathly_orchestrator.runner.next_action"
_COMPLETE_STAGE_PATH = "pathly_orchestrator.runner.complete_stage"
_INVOKE_AGENT_PATH = "pathly_orchestrator.runner.invoke_agent"


def _na_state(state: str = "STORMING") -> dict:
    return {
        "current_state": state,
        "agent": "team/storm",
        "instructions": "do stuff",
        "limits": {},
    }


def _cs_next(from_: str = "STORMING", to: str = "PLANNING") -> dict:
    return {
        "next_state": to,
        "agent": "team/plan",
        "instructions": "plan stuff",
        "limits": {},
    }


def _cs_done() -> dict:
    return {"done": True}


# ── run_flow: happy path (single stage → done) ────────────────────────────────


def test_run_flow_single_stage_done(capsys):
    with (
        patch(_NEXT_ACTION_PATH, return_value=_na_state()) as mock_na,
        patch(_INVOKE_AGENT_PATH) as mock_invoke,
        patch(_COMPLETE_STAGE_PATH, return_value=_cs_done()) as mock_cs,
    ):
        rc = run_flow("team", "my-topic", "/proj")
    assert rc == 0
    mock_na.assert_called_once_with(
        {"flow": "team", "topic": "my-topic", "project_root": "/proj"}
    )
    mock_invoke.assert_called_once()
    out = capsys.readouterr().out
    assert "✓ Complete" in out


# ── run_flow: multi-stage ─────────────────────────────────────────────────────


def test_run_flow_multi_stage(capsys):
    na_calls = [_na_state("STORMING"), _na_state("PLANNING")]
    cs_calls = [_cs_next("STORMING", "PLANNING"), _cs_done()]
    with (
        patch(_NEXT_ACTION_PATH, side_effect=na_calls),
        patch(_INVOKE_AGENT_PATH),
        patch(_COMPLETE_STAGE_PATH, side_effect=cs_calls),
    ):
        rc = run_flow("team", "my-topic", "/proj")
    assert rc == 0
    out = capsys.readouterr().out
    assert "STORMING → PLANNING" in out
    assert "✓ Complete" in out


# ── run_flow: blocked on human before first stage ────────────────────────────


def test_run_flow_blocked_human(capsys):
    blocked = {
        "blocked": True,
        "target_agent": "human",
        "file": "HUMAN_QUESTIONS.md",
        "instructions": "Answer me!",
    }
    with (
        patch(_NEXT_ACTION_PATH, return_value=blocked),
        patch(_INVOKE_AGENT_PATH),
    ):
        rc = run_flow("team", "my-topic", "/proj")
    assert rc == 1
    out = capsys.readouterr().out
    assert "Human checkpoint" in out


# ── handle_decide: valid input ────────────────────────────────────────────────


def test_handle_decide_valid_input():
    response = {
        "decide": True,
        "question": "Which path?",
        "options": {"a": "PATH_A", "b": "PATH_B"},
        "default": "a",
    }
    with (
        patch("builtins.input", return_value="b"),
        patch(_COMPLETE_STAGE_PATH, return_value=_cs_done()) as mock_cs,
    ):
        result = handle_decide("team", "topic", "/proj", response)
    mock_cs.assert_called_once_with(
        {
            "flow": "team",
            "topic": "topic",
            "project_root": "/proj",
            "decision": "b",
        }
    )
    assert result == _cs_done()


# ── handle_decide: invalid input falls back to default ───────────────────────


def test_handle_decide_invalid_input_uses_default():
    response = {
        "decide": True,
        "question": "Which path?",
        "options": {"a": "PATH_A", "b": "PATH_B"},
        "default": "a",
    }
    with (
        patch("builtins.input", return_value="zzz"),
        patch(_COMPLETE_STAGE_PATH, return_value=_cs_done()) as mock_cs,
    ):
        handle_decide("team", "topic", "/proj", response)
    mock_cs.assert_called_once_with(
        {
            "flow": "team",
            "topic": "topic",
            "project_root": "/proj",
            "decision": "a",
        }
    )


# ── resolve_stage: feedback resolved on second call ──────────────────────────


def test_resolve_stage_feedback_once():
    blocked = {
        "blocked": True,
        "target_agent": "reviewer",
        "file": "REVIEW.md",
        "instructions": "fix it",
    }
    cs_sequence = [blocked, _cs_done()]
    with (
        patch(_COMPLETE_STAGE_PATH, side_effect=cs_sequence) as mock_cs,
        patch(_INVOKE_AGENT_PATH),
    ):
        result = resolve_stage(
            "team", "topic", "/proj", "claude-sonnet-4-6", "REVIEWING"
        )
    assert result.get("done") is True
    assert mock_cs.call_count == 2
    # second call passes resolved_files
    second_call_args = mock_cs.call_args_list[1][0][0]
    assert second_call_args["resolved_files"] == ["REVIEW.md"]


# ── resolve_stage: exceeds MAX_FEEDBACK_ROUNDS ───────────────────────────────


def test_resolve_stage_exceeds_max_feedback_rounds(tmp_path):
    blocked = {
        "blocked": True,
        "target_agent": "reviewer",
        "file": "REVIEW.md",
        "instructions": "fix it",
    }
    # Returns blocked 4 times (exceeds MAX_FEEDBACK_ROUNDS=3), then done
    cs_calls = [blocked] * 4 + [_cs_done()]
    with (
        patch(_COMPLETE_STAGE_PATH, side_effect=cs_calls),
        patch(_INVOKE_AGENT_PATH),
        patch("pathly_orchestrator.runner._storage_path", return_value=tmp_path),
        patch("builtins.input", return_value=""),
    ):
        result = resolve_stage(
            "team", "topic", "/proj", "claude-sonnet-4-6", "REVIEWING"
        )
    escalation = tmp_path / "feedback" / "HUMAN_QUESTIONS.md"
    assert escalation.exists()
    assert "Escalation" in escalation.read_text()
    assert result.get("done") is True


# ── invoke_agent: timeout raises RuntimeError ────────────────────────────────


def test_invoke_agent_timeout():
    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
        cmd="claude", timeout=1
    )
    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="timed out"):
            invoke_agent("do stuff", "/proj", "claude-sonnet-4-6", timeout=1)
    mock_proc.kill.assert_called_once()


# ── invoke_agent: non-zero exit raises RuntimeError ──────────────────────────


def test_invoke_agent_nonzero_exit():
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"{}", None)
    mock_proc.returncode = 1
    with patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="exited with code 1"):
            invoke_agent("do stuff", "/proj", "claude-sonnet-4-6")


def test_resolve_argv_claude_adds_json_output():
    argv = resolve_argv("claude", "prompt", "model")
    assert "--output-format=json" in argv


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"cost_usd": 1.25, "session_id": "s1"}', (1.25, "s1")),
        ('\x1b[31m{"cost_usd": 2, "session_id": "s2"}\x1b[0m', (2.0, "s2")),
        ("", (0.0, None)),
        ('{"cost_usd": 1}\n{"cost_usd": 3, "session_id": "s3"}\n', (3.0, "s3")),
        ('{"cost_usd": 4, "session_id": "s4"\n', (0.0, None)),
        ('{"total_cost_usd": 5, "sessionId": "s5"}\nDone.', (5.0, "s5")),
    ],
)
def test_parse_result_cases(raw, expected):
    cost, session_id = expected
    result = parse_result("claude", raw)
    assert result["cost_usd"] == cost
    assert result["session_id"] == session_id


def test_parse_result_codex_shape_drift():
    result = parse_result("codex", '{"cost": 6, "sessionId": "codex-1"}')
    assert result["cost_usd"] == 6.0
    assert result["session_id"] == "codex-1"
    assert result["ask_user_question"] is None
    assert result["result"] == ""
    assert result["tokens_in"] == 0
    assert result["tokens_out"] == 0
    assert result["tool_uses"] == 0


# ── codex `exec --json` JSONL token-usage capture (defensive — shape unconfirmed) ──


def test_parse_result_codex_captures_tokens_from_typed_token_count_event():
    raw = (
        '{"type": "session_start", "session_id": "codex-abc"}\n'
        '{"type": "token_count", "input_tokens": 1200, "output_tokens": 340}\n'
        '{"type": "agent_message", "text": "done"}\n'
    )
    result = parse_result("codex", raw)
    assert result["tokens_in"] == 1200
    assert result["tokens_out"] == 340
    assert result["cost_usd"] == 0.0  # codex never emits a dollar cost


def test_parse_result_codex_captures_nested_usage_field():
    raw = '{"usage": {"prompt_tokens": 500, "completion_tokens": 90}}'
    result = parse_result("codex", raw)
    assert result["tokens_in"] == 500
    assert result["tokens_out"] == 90


def test_parse_result_codex_captures_info_total_token_usage():
    # Real-world session-rollout shape: cached is INSIDE input and reasoning is INSIDE output
    # (total_tokens == input_tokens + output_tokens), so neither is summed on top.
    raw = (
        '{"info": {"total_token_usage": {"input_tokens": 2000, '
        '"cached_input_tokens": 300, "output_tokens": 150, '
        '"reasoning_output_tokens": 40}}}'
    )
    result = parse_result("codex", raw)
    assert (
        result["tokens_in"] == 2000
    )  # cached_input_tokens (300) already inside input_tokens
    assert (
        result["tokens_out"] == 150
    )  # reasoning_output_tokens (40) already inside output_tokens


def test_parse_result_codex_keeps_last_nonzero_usage_event():
    raw = (
        '{"usage": {"input_tokens": 100, "output_tokens": 20}}\n'
        '{"usage": {"input_tokens": 400, "output_tokens": 80}}\n'
    )
    result = parse_result("codex", raw)
    assert result["tokens_in"] == 400
    assert result["tokens_out"] == 80


def test_parse_result_codex_no_usage_event_yields_zero_tokens():
    raw = '{"type": "agent_message", "text": "hello"}\n'
    result = parse_result("codex", raw)
    assert result["tokens_in"] == 0
    assert result["tokens_out"] == 0


# ── tail_agent_done ───────────────────────────────────────────────────────────


def test_tail_agent_done_yields_and_stops(tmp_path):
    import threading
    import time
    import json
    from pathly_orchestrator.runner import tail_agent_done

    events_file = tmp_path / "EVENTS.jsonl"
    build_start = {"type": "BUILD_START", "ts": "2026-01-01T00:00:00Z"}
    events_file.write_text(json.dumps(build_start) + "\n", encoding="utf-8")

    after_ts = "2026-01-01T00:00:00Z"
    stop_evt = threading.Event()
    results = []

    def _run():
        for event in tail_agent_done(
            str(events_file), after_ts, stop_evt, poll_interval=0.05
        ):
            results.append(event)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    agent_done = {"type": "AGENT_DONE", "ts": "2026-01-01T00:01:00Z", "result": "DONE"}
    with open(str(events_file), "ab") as f:
        f.write((json.dumps(agent_done) + "\n").encode("utf-8"))

    deadline = time.monotonic() + 2.0
    while not results and time.monotonic() < deadline:
        time.sleep(0.05)

    stop_evt.set()
    thread.join(timeout=2.0)

    assert len(results) == 1
    assert results[0]["type"] == "AGENT_DONE"


# ── build_pipeline_history_block ──────────────────────────────────────────────


def test_pipeline_history_block_format(tmp_path):
    import json
    from pathly_orchestrator.runner import build_pipeline_history_block

    events_path = tmp_path / "EVENTS.jsonl"
    entries = [
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 1,
            "summary": "added event constant",
            "ts": "2026-01-01T00:00:01Z",
        },
        {
            "type": "AGENT_DONE",
            "agent": "reviewer",
            "conversation": 1,
            "summary": "review PASS",
            "ts": "2026-01-01T00:00:02Z",
        },
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 2,
            "summary": "wired supervisor",
            "ts": "2026-01-01T00:00:03Z",
        },
    ]
    events_path.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )

    block = build_pipeline_history_block(str(events_path))

    assert block.startswith("\n## Pipeline History\n")
    assert "- **builder (conv 1)**: added event constant" in block
    assert "- **reviewer (conv 1)**: review PASS" in block
    assert "- **builder (conv 2)**: wired supervisor" in block
    lines = [l for l in block.splitlines() if l.startswith("- ")]
    assert lines[0] == "- **builder (conv 1)**: added event constant"
    assert lines[2] == "- **builder (conv 2)**: wired supervisor"


def test_pipeline_history_empty_when_no_events(tmp_path):
    import json
    from pathly_orchestrator.runner import build_pipeline_history_block

    # Non-existent path returns ""
    assert build_pipeline_history_block(str(tmp_path / "nonexistent.jsonl")) == ""

    # File with no AGENT_DONE lines returns ""
    events_path = tmp_path / "EVENTS.jsonl"
    events_path.write_text(
        json.dumps(
            {"type": "PHASE_START", "phase": "build", "ts": "2026-01-01T00:00:00Z"}
        )
        + "\n",
        encoding="utf-8",
    )
    assert build_pipeline_history_block(str(events_path)) == ""
