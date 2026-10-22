"""chief-agent 06: opening and closing a chief session in the supervisor.

``runner/chief_argv.py`` (pure) builds the chief's argv and claude settings;
``supervisor/chief_session.py`` mints the token, writes the session folder, registers the
session, sends one interactive ``TERMINAL_SPAWN`` (prompt pasted, not submitted) and closes the
session when the tab goes away. A fake broadcaster stands in for the spawn host: it only records
the payload, and the test marks the run started and finished the way the host's callbacks do.

The tests never patch the global ``time.sleep`` (the WAL checkpoint daemon shares it); the
watcher thread is waited for with a bounded poll on ``time.monotonic()``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from _paths import SRC
from chief_session_guard import _no_watcher_outlives_its_test

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.db.queries.run_tokens import (
    lookup_run_token,
    resolve_run_token,
)
from pathly_orchestrator.runner.chief_argv import chief_argv, claude_settings
from pathly_orchestrator.supervisor import chief_session
from pathly_orchestrator.supervisor.chief_session import (
    ChiefAlreadyOpen,
    close_chief,
    open_chief,
)
from pathly_orchestrator.supervisor.registry import get_run

PROMPT = "---\ntier: operator\n---\nYou are the chief of this project."
BODY = "You are the chief of this project."


def _fragment() -> str:
    """The fixed rules the server appends to every chief prompt, as the file holds them."""
    path = SRC / "pathly_data" / "core" / "skills" / "fragments" / "chief-connect.md"
    return path.read_text(encoding="utf-8").strip()


DENY = [
    "Edit",
    "Write",
    "NotebookEdit",
    "Agent",
    "CronCreate",
    "Workflow",
    "WebFetch",
    "WebSearch",
    "Read(~/.pathly/**)",
    "Bash(curl *)",
    "Bash(wget *)",
]


class Host:
    """The spawn host's side of the contract: it only records what it was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __call__(self, topic: str, payload: dict) -> None:
        self.sent.append((topic, payload))

    @property
    def payload(self) -> dict:
        assert len(self.sent) == 1, self.sent
        return self.sent[0][1]


@pytest.fixture()
def project(tmp_path: Path) -> str:
    root = tmp_path / "proj"
    root.mkdir()
    return str(root)


@pytest.fixture()
def chief_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The sessions folder, under a name with a space so the hook command must quote it."""
    root = tmp_path / "chief sessions"
    monkeypatch.setattr(chief_session, "_chief_root", lambda: root)
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8123")
    return root


def _open(project: str, host: Host, **overrides) -> dict:
    args = dict(
        project_root=project,
        engine="claude",
        preset="operator",
        prompt=PROMPT,
        broadcast_fn=host,
    )
    args.update(overrides)
    return open_chief(**args)


def _wait(done, seconds: float = 5.0) -> bool:
    """A bounded poll on the monotonic clock (not a patched sleep)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if done():
            return True
        time.sleep(0.01)
    return done()


def _watchers(run_id: str) -> list[threading.Thread]:
    return [t for t in threading.enumerate() if run_id in t.name and t.is_alive()]


def _finish(run_id: str) -> None:
    """What Studio's started and result callbacks do."""
    run = get_run(run_id)
    assert run is not None
    run.mark_started()
    run.mark_pty_result({"exit_code": 0})


def _value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


# ── chief_argv and claude_settings (pure) ────────────────────────────────────────


def test_claude_argv_is_restricted_with_its_own_tools_settings_mcp_and_session():
    argv = chief_argv("claude", "", "/s/settings.json", "/s/mcp.json", "sess-1")
    assert argv == [
        "claude",
        "--restricted",
        "--tools",
        "Bash,Read,Glob,Grep",
        "--settings",
        "/s/settings.json",
        "--mcp-config",
        "/s/mcp.json",
        "--strict-mcp-config",
        "--session-id",
        "sess-1",
    ]


def test_claude_argv_adds_the_model_pair_only_when_a_model_is_given():
    assert "--model" not in chief_argv("claude", "", "s", "m", "x")
    argv = chief_argv("claude", "opus", "s", "m", "x")
    assert argv[-2:] == ["--model", "opus"]


def test_codex_argv_is_read_only_and_asks_before_every_command():
    argv = chief_argv("codex", "", "s", "m", None)
    assert argv == [
        "codex",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "on-request",
    ]
    assert chief_argv("codex", "gpt-5", "s", "m", None)[-2:] == ["--model", "gpt-5"]
    assert "--session-id" not in argv


@pytest.mark.parametrize("engine", ["copilot", "antigravity", "", "Claude"])
def test_any_other_engine_is_a_value_error(engine):
    with pytest.raises(ValueError):
        chief_argv(engine, "", "s", "m", "x")


@pytest.mark.parametrize("session_id", [None, ""])
def test_a_claude_chief_needs_the_session_id_the_server_chose(session_id):
    with pytest.raises(ValueError):
        chief_argv("claude", "", "s", "m", session_id)


@pytest.mark.parametrize("engine", ["claude", "codex"])
def test_argv_never_bypasses_permissions(engine):
    argv = chief_argv(engine, "m", "s", "m", "x")
    assert not [a for a in argv if "dangerously" in a or "bypass" in a]


def test_claude_settings_allow_only_pathly_and_deny_the_rest():
    settings = claude_settings("echo hook")
    assert settings["permissions"]["allow"] == ["Bash(pathly *)"]
    assert settings["permissions"]["deny"] == DENY
    assert settings["hooks"] == {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo hook"}]}]
    }


# ── open_chief ───────────────────────────────────────────────────────────────────


def test_open_emits_one_interactive_spawn_that_pastes_without_enter(
    project, chief_root
):
    host = Host()
    out = _open(project, host)
    topic, payload = host.sent[0]
    assert len(host.sent) == 1
    run_id = out["run_id"]
    assert run_id == out["tab_id"] == payload["tab_id"] == payload["run_id"]
    assert len(run_id) == len("chief-") + 12 and run_id.startswith("chief-")
    int(run_id[len("chief-") :], 16)
    assert topic == payload["topic"] == "chief:" + run_id
    assert payload["type"] == "TERMINAL_SPAWN"
    assert payload["interactive"] is True
    assert payload["submit"] is False
    # The style without its front matter, then the fixed rules the server appends (ticket 17).
    assert payload["prompt"].startswith(BODY + "\n\n" + _fragment())
    assert payload["label"] == "Chief · Operator"
    assert payload["adapter"] == "claude"
    assert payload["cwd"] == project
    assert payload["category"] == "single"
    assert out == {
        "run_id": run_id,
        "tab_id": run_id,
        "tier": "operator",
        "engine": "claude",
    }


def test_the_token_is_a_chief_token_for_the_project_board_and_is_never_in_argv_or_prompt(
    project, chief_root
):
    from pathly_orchestrator.fsm_compose import resolve_board_scope

    host = Host()
    run_id = _open(project, host)["run_id"]
    payload = host.payload
    token = payload["run_token"]
    live = resolve_run_token(get_db(), token)
    assert live is not None
    assert live["role"] == "chief"
    assert live["board"] == "project"
    assert live["run_id"] == run_id
    assert live["scope"] == resolve_board_scope("project", project, "")
    assert live["project_root"] == project
    assert token not in payload["prompt"]
    assert token not in " ".join(payload["argv"])
    for path in (chief_root / run_id).iterdir():
        assert token not in path.read_text(encoding="utf-8")


def test_claude_argv_in_the_spawn_names_the_session_files_and_the_stored_session_id(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host, model="opus")["run_id"]
    argv = host.payload["argv"]
    folder = chief_root / run_id
    assert argv[0] == "claude"
    assert _value(argv, "--settings") == str(folder / "settings.json")
    assert "--strict-mcp-config" in argv
    mcp = Path(_value(argv, "--mcp-config"))
    assert json.loads(mcp.read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert _value(argv, "--tools") == "Bash,Read,Glob,Grep"
    assert "--restricted" in argv or _value(argv, "--setting-sources") == ""
    assert _value(argv, "--model") == "opus"
    assert "--dangerously-skip-permissions" not in argv
    session_id = _value(argv, "--session-id")
    assert str(uuid.UUID(session_id)) == session_id
    session = chief_queries.get_session(get_db(), run_id)
    assert session["cli_session_id"] == session_id


def test_codex_argv_is_read_only_with_no_session_id_and_no_claude_files(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host, engine="codex", preset="status")["run_id"]
    argv = host.payload["argv"]
    assert argv[0] == "codex"
    assert _value(argv, "--sandbox") == "read-only"
    assert "--session-id" not in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    assert chief_queries.get_session(get_db(), run_id)["cli_session_id"] is None
    assert sorted(p.name for p in (chief_root / run_id).iterdir()) == ["hook_secret"]
    assert host.payload["label"] == "Chief · Status"


def test_the_settings_file_holds_the_hook_command_and_the_deny_list(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host)["run_id"]
    folder = chief_root / run_id
    settings = json.loads((folder / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["allow"] == ["Bash(pathly *)"]
    deny = settings["permissions"]["deny"]
    assert {"Bash(curl *)", "Bash(wget *)", "WebFetch"} <= set(deny)
    assert deny == DENY
    (entry,) = settings["hooks"]["UserPromptSubmit"]
    (hook,) = entry["hooks"]
    assert hook["type"] == "command"
    assert shlex.split(hook["command"]) == [
        sys.executable,
        "-m",
        "pathly_hooks.chief_prompt",
        "--run-id",
        run_id,
        "--secret-file",
        str(folder / "hook_secret"),
        "--port",
        "8123",
    ]


def test_the_session_row_stores_the_hash_of_the_secret_the_folder_holds(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host, preset="planner", prompt="Plan things.")["run_id"]
    folder = chief_root / run_id
    secret = (folder / "hook_secret").read_text(encoding="utf-8")
    assert len(secret) >= 32
    session = chief_queries.get_session(get_db(), run_id)
    assert session["hook_secret_hash"] == hashlib.sha256(secret.encode()).hexdigest()
    assert (session["project_root"], session["preset"], session["tier"]) == (
        project,
        "planner",
        "planner",
    )
    assert (session["engine"], session["tab_id"]) == ("claude", run_id)
    assert session["settings_dir"] == str(folder)
    assert session["closed_at"] is None
    assert secret not in json.dumps(host.payload)
    assert not [p for p in folder.iterdir() if secret in p.name]


def test_the_session_files_are_private_on_posix(project, chief_root):
    host = Host()
    run_id = _open(project, host)["run_id"]
    if os.name == "posix":
        for name in ("hook_secret", "settings.json", "mcp.json"):
            mode = (chief_root / run_id / name).stat().st_mode & 0o777
            assert mode == 0o600, name


def test_a_second_open_for_the_project_raises_with_the_open_tab(project, chief_root):
    host = Host()
    first = _open(project, host)
    with pytest.raises(ChiefAlreadyOpen) as raised:
        _open(project, host)
    assert raised.value.run_id == first["run_id"]
    assert raised.value.tab_id == first["tab_id"]
    assert len(host.sent) == 1


def test_another_project_may_open_its_own_chief(project, chief_root, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    host = Host()
    first = _open(project, host)
    second = _open(str(other), host)
    assert first["run_id"] != second["run_id"]


def test_a_new_chief_may_open_once_the_old_one_is_closed(project, chief_root):
    host = Host()
    first = _open(project, host)
    assert close_chief(first["run_id"], "closed by the user") is True
    second = _open(project, host)
    assert second["run_id"] != first["run_id"]


@pytest.mark.parametrize("engine", ["copilot", "antigravity", "", None])
def test_an_unsupported_engine_is_a_value_error(project, chief_root, engine):
    host = Host()
    with pytest.raises(ValueError):
        _open(project, host, engine=engine)
    assert host.sent == []


MISSING_FOLDER = (
    object()
)  # a project root that does not exist: built from tmp_path in the test

BAD_INPUTS = [
    pytest.param("project_root", MISSING_FOLDER, id="project_root-missing-folder"),
    pytest.param("project_root", "", id="project_root-empty"),
    pytest.param("project_root", None, id="project_root-none"),
    pytest.param("prompt", "", id="prompt-empty"),
    pytest.param("prompt", "   \n", id="prompt-blank"),
    pytest.param("prompt", 3, id="prompt-number"),
    pytest.param("prompt", "x" * (64 * 1024 + 1), id="prompt-over-64-kib"),
    pytest.param("model", "--dangerously-skip-permissions", id="model-an-option"),
    pytest.param("model", 3, id="model-number"),
    pytest.param("preset", None, id="preset-none"),
]


@pytest.mark.parametrize("field,value", BAD_INPUTS)
def test_bad_input_is_a_value_error_and_leaves_nothing_behind(
    project, chief_root, tmp_path, field, value
):
    if value is MISSING_FOLDER:
        value = str(tmp_path / "missing")
    host = Host()
    with pytest.raises(ValueError):
        _open(project, host, **{field: value})
    assert host.sent == []
    assert chief_queries.open_session_for_project(get_db(), project) is None
    assert not chief_root.exists() or not list(chief_root.iterdir())


def test_a_prompt_of_exactly_64_kib_is_accepted_and_the_fixed_rules_follow_it(
    project, chief_root
):
    host = Host()
    _open(project, host, prompt="x" * (64 * 1024))
    # The limit is on the style as given, checked before the fragment is appended.
    assert host.payload["prompt"].startswith("x" * (64 * 1024) + "\n\n" + _fragment())


@pytest.mark.parametrize("preset", ["status", "planner", "operator"])
def test_without_a_prompt_a_built_in_preset_uses_its_built_in_text(
    project, chief_root, preset
):
    from pathly_orchestrator.supervisor import chief_presets

    host = Host()
    out = _open(project, host, preset=preset, prompt=None)
    assert out["tier"] == preset
    assert host.payload["prompt"].startswith(
        chief_presets.BUILT_IN[preset].strip() + "\n\n" + _fragment()
    )


@pytest.mark.parametrize("preset", ["custom", "", "Operator", "operator "])
def test_without_a_prompt_any_other_preset_is_a_value_error_and_leaves_nothing(
    project, chief_root, preset
):
    host = Host()
    with pytest.raises(ValueError, match="prompt"):
        _open(project, host, preset=preset, prompt=None)
    assert host.sent == []
    assert chief_queries.open_session_for_project(get_db(), project) is None
    assert not chief_root.exists() or not list(chief_root.iterdir())


def test_a_failed_broadcast_rolls_the_whole_open_back(project, chief_root):
    seen: dict = {}

    def boom(topic: str, payload: dict) -> None:
        seen.update(payload)
        raise RuntimeError("host is down")

    with pytest.raises(RuntimeError):
        _open(project, boom)
    run_id = seen["run_id"]
    assert resolve_run_token(get_db(), seen["run_token"]) is None
    assert lookup_run_token(get_db(), seen["run_token"])["revoked_at"] is not None
    assert not (chief_root / run_id).exists()
    assert get_run(run_id) is None
    assert chief_queries.open_session_for_project(get_db(), project) is None
    assert chief_queries.get_session(get_db(), run_id)["close_reason"] == "open failed"
    assert _wait(lambda: not _watchers(run_id))


# ── the watcher and close_chief ──────────────────────────────────────────────────


def test_when_the_tab_exits_the_token_is_revoked_and_the_folder_is_gone(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host)["run_id"]
    token = host.payload["run_token"]
    folder = chief_root / run_id
    assert folder.is_dir() and get_run(run_id) is not None
    assert resolve_run_token(get_db(), token) is not None

    run = get_run(run_id)
    run.mark_started()
    run.mark_pty_result({"exit_code": 0})

    assert _wait(lambda: get_run(run_id) is None)
    assert resolve_run_token(get_db(), token) is None
    assert lookup_run_token(get_db(), token)["revoked_at"] is not None
    assert not folder.exists()
    session = chief_queries.get_session(get_db(), run_id)
    assert session["closed_at"] is not None
    assert session["close_reason"] == "tab closed"
    assert chief_queries.open_session_for_project(get_db(), project) is None
    assert _wait(lambda: not _watchers(run_id))


def test_a_chief_that_never_starts_is_closed_as_never_started(project, chief_root):
    host = Host()
    run_id = _open(project, host, start_timeout=0.05)["run_id"]
    token = host.payload["run_token"]
    # Dropping the run is the last step of the close, so wait for it before the rest.
    assert _wait(lambda: get_run(run_id) is None)
    session = chief_queries.get_session(get_db(), run_id)
    assert session["closed_at"] is not None
    assert session["close_reason"] == "never started"
    assert resolve_run_token(get_db(), token) is None
    assert not (chief_root / run_id).exists()


def test_a_started_chief_is_not_closed_by_the_start_timeout(project, chief_root):
    class StartingHost(Host):
        def __call__(self, topic: str, payload: dict) -> None:
            super().__call__(topic, payload)
            get_run(payload["run_id"]).mark_started()

    host = StartingHost()
    run_id = _open(project, host, start_timeout=0.05)["run_id"]
    # Well past the start timeout; the tab started, so the session stays open.
    assert not _wait(
        lambda: chief_queries.get_session(get_db(), run_id)["closed_at"], seconds=0.4
    )
    assert get_run(run_id) is not None
    _finish(run_id)
    assert _wait(lambda: chief_queries.get_session(get_db(), run_id)["closed_at"])
    assert chief_queries.get_session(get_db(), run_id)["close_reason"] == "tab closed"


def test_close_chief_closes_once_and_is_safe_to_call_twice(project, chief_root):
    host = Host()
    run_id = _open(project, host)["run_id"]
    token = host.payload["run_token"]
    assert close_chief(run_id, "closed by the user") is True
    assert close_chief(run_id, "closed again") is False
    assert resolve_run_token(get_db(), token) is None
    assert not (chief_root / run_id).exists()
    assert get_run(run_id) is None
    session = chief_queries.get_session(get_db(), run_id)
    assert session["close_reason"] == "closed by the user"


def test_close_chief_lets_the_watcher_go(project, chief_root):
    host = Host()
    run_id = _open(project, host)["run_id"]
    get_run(run_id).mark_started()
    assert _watchers(run_id)
    close_chief(run_id, "closed by the user")
    assert _wait(lambda: not _watchers(run_id))
    assert (
        chief_queries.get_session(get_db(), run_id)["close_reason"]
        == "closed by the user"
    )


def test_close_chief_for_an_unknown_run_is_false_and_touches_no_other_folder(
    project, chief_root
):
    host = Host()
    run_id = _open(project, host)["run_id"]
    assert close_chief("chief-000000000000", "x") is False
    assert close_chief("../" + run_id, "x") is False
    assert (chief_root / run_id).is_dir()
    assert chief_queries.get_session(get_db(), run_id)["closed_at"] is None
