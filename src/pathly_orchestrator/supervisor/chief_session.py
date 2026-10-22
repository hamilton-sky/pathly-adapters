"""Open and close a chief session (chief-agent).

The chief is a long-lived interactive spawn, so it cannot go through
``terminal._run_stage_via_terminal``: that call blocks its caller until the process exits and
gives up after 30 minutes. ``open_chief`` builds the same pieces by hand (a run token, a run
registered for the host's callbacks, one ``TERMINAL_SPAWN``) and returns at once; a watcher
thread closes the session when the host reports the tab started and then exited (or exited with
no "started" at all), or never started. Studio's result post and ``pathly-pty-host``'s refusal
of an interactive spawn both reach the watcher through the existing ``/runner/terminal/result``
handler, which finds the run with ``registry.get_run``.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import sys
import threading
import uuid
from pathlib import Path
from typing import Callable

from pathly_orchestrator.config import Settings
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries import chief as queries
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, revoke_run_tokens
from pathly_orchestrator.runner.chief_argv import chief_argv, claude_settings

from .chief_presets import BUILT_IN, compose_prompt, default_style
from .chief_tiers import resolve_preset_tier, strip_front_matter
from .registry import create_run, drop_run, get_run
from .state import logger

ENGINES = ("claude", "codex")
MAX_PROMPT_BYTES = 64 * 1024

_RUN_ID_RE = re.compile(r"chief-[0-9a-f]{12}")
_open_lock = threading.Lock()


class ChiefAlreadyOpen(Exception):
    """The project already has an open chief; carries the open tab so the caller can show it."""

    def __init__(self, run_id: str, tab_id: str) -> None:
        super().__init__(f"a chief is already open for this project ({tab_id})")
        self.run_id = run_id
        self.tab_id = tab_id


class ChiefClosedWhileOpening(Exception):
    """The session was closed while ``open_chief`` was opening it; nothing was left live.

    Carries the run id of the closed session. ``POST /chief/open`` answers it as a 409.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__(f"the chief {run_id} was closed while it was opening")
        self.run_id = run_id


def _chief_root() -> Path:
    """Where session folders live; a function so a test can point it elsewhere."""
    return Path.home() / ".pathly" / "chief"


def normalise_project_root(project_root: str) -> str:
    """The key a project's chief is registered and looked up under: forward slashes, no
    trailing slash (the form the board code uses), so ``/p`` and ``/p/`` are one project.
    """
    return project_root.replace("\\", "/").rstrip("/") or project_root


def _validate(
    project_root: object, engine: object, preset: object, model: object
) -> None:
    if engine not in ENGINES:
        raise ValueError(f"the chief runs on claude or codex, not {engine!r}")
    if not isinstance(project_root, str) or not os.path.isdir(project_root):
        raise ValueError("project_root must be an existing directory")
    if not isinstance(preset, str):
        raise ValueError("preset must be a string")
    if not isinstance(model, str) or model.startswith("-"):
        raise ValueError("model must be a string that does not start with '-'")


def _style(preset: str, prompt: object, project_root: str) -> str:
    """The style to paste: the caller's ``prompt``, else the user's file ``chief/<preset>``,
    else the built-in text of a built-in preset. A style is checked as given, before the fixed
    rules are appended."""
    if prompt is None:
        prompt = default_style(preset, project_root)
        if prompt is None:
            raise ValueError(
                f"prompt is required for preset {preset!r}: only "
                f"{', '.join(BUILT_IN)} have a built-in text"
            )
    if not isinstance(prompt, str) or not strip_front_matter(prompt).strip():
        raise ValueError("prompt must be a non-empty string")
    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise ValueError(f"prompt must be at most {MAX_PROMPT_BYTES} bytes")
    return prompt


def _write_private(path: Path, text: str) -> None:
    """Create ``path`` readable by its owner only (the mode is set at creation, not after)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _hook_command(run_id: str, secret_file: Path) -> str:
    port = Settings.from_env().port
    return " ".join(
        [
            shlex.quote(sys.executable),
            "-m",
            "pathly_hooks.chief_prompt",
            "--run-id",
            shlex.quote(run_id),
            "--secret-file",
            shlex.quote(str(secret_file)),
            "--port",
            str(port),
        ]
    )


def _write_session_folder(folder: Path, engine: str, run_id: str) -> str:
    """Write the folder's files; returns the sha256 of the hook secret."""
    folder.mkdir(parents=True, mode=0o700)
    secret = secrets.token_urlsafe(32)
    secret_file = folder / "hook_secret"
    _write_private(secret_file, secret)
    if engine == "claude":
        settings = claude_settings(_hook_command(run_id, secret_file))
        _write_private(folder / "settings.json", json.dumps(settings, indent=2))
        _write_private(folder / "mcp.json", json.dumps({"mcpServers": {}}))
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _remove_folder(run_id: str) -> None:
    folder = _chief_root() / run_id
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("chief: could not remove %s", folder, exc_info=True)


def open_chief(
    *,
    project_root: str,
    engine: str,
    preset: str,
    prompt: str | None = None,
    model: str = "",
    broadcast_fn: Callable[[str, dict], None],
    start_timeout: float = 30.0,
) -> dict:
    """Open a chief for ``project_root`` and send its interactive ``TERMINAL_SPAWN``.

    Raises ``ValueError`` for a bad engine, directory, prompt (empty, or over 64 KiB) or model,
    and ``ChiefAlreadyOpen`` when the project has an open chief. ``project_root`` is
    normalised (``normalise_project_root``) before anything is stored or compared. Returns
    ``{run_id, tab_id, tier, engine}`` without waiting for the tab.

    ``prompt`` is the chief's style. Left out, the style is the user's file ``chief/<preset>``,
    else the built-in text of ``status``, ``planner`` or ``operator`` (any other preset needs a
    prompt). What is pasted is the style without its front matter, the ``chief-connect``
    fragment and the stored project root (``chief_presets.compose_prompt``); the 64 KiB limit is
    on the style, checked before anything is appended.

    ``POST /chief/close`` does not take the lock that guards the session row, so a close can
    land while this opens. Once the token is minted the session is read again: if it is closed
    the token is revoked, no spawn is sent and ``ChiefClosedWhileOpening`` is raised. A close
    that lands after that re-read and before the broadcast cannot be shut out without holding
    a lock across the broadcast; it still revokes the token, so the tab starts with a dead one
    and the watcher closes the (already closed) session as soon as the tab reports its end.
    """
    _validate(project_root, engine, preset, model)
    project_root = normalise_project_root(project_root)
    pasted = compose_prompt(_style(preset, prompt, project_root), project_root)
    conn = get_db()
    tier = resolve_preset_tier(preset, project_root)
    run_id = "chief-" + secrets.token_hex(6)
    folder = _chief_root() / run_id
    cli_session_id = str(uuid.uuid4()) if engine == "claude" else None

    with _open_lock:
        existing = queries.open_session_for_project(conn, project_root)
        if existing is not None:
            raise ChiefAlreadyOpen(existing["run_id"], existing["tab_id"])
        try:
            secret_hash = _write_session_folder(folder, engine, run_id)
            queries.create_session(
                conn,
                run_id=run_id,
                project_root=project_root,
                preset=preset or None,
                tier=tier,
                engine=engine,
                tab_id=run_id,
                cli_session_id=cli_session_id,
                hook_secret_hash=secret_hash,
                settings_dir=str(folder),
            )
        except BaseException:
            _remove_folder(run_id)
            raise

    try:
        from pathly_orchestrator.fsm_compose import resolve_board_scope

        scope = resolve_board_scope("project", project_root, "")
        token = mint_run_token(
            conn, run_id, "chief", None, project_root, "project", scope
        )
        if not _is_open(conn, run_id):
            revoke_run_tokens(conn, run_id)
            raise ChiefClosedWhileOpening(run_id)
        argv = chief_argv(
            engine,
            model,
            str(folder / "settings.json"),
            str(folder / "mcp.json"),
            cli_session_id,
        )
        run = create_run(run_id)
        broadcast_fn(
            "chief:" + run_id,
            {
                "type": "TERMINAL_SPAWN",
                "topic": "chief:" + run_id,
                "run_id": run_id,
                "run_token": token,
                "tab_id": run_id,
                "label": "Chief · " + tier.title(),
                "adapter": engine,
                "argv": argv,
                "cwd": project_root,
                "prompt": pasted,
                "interactive": True,
                "submit": False,
                "category": "single",
            },
        )
    except BaseException:
        close_chief(run_id, "open failed")
        raise

    threading.Thread(
        target=_watch,
        args=(run, run_id, start_timeout),
        daemon=True,
        name=f"chief-watch-{run_id}",
    ).start()
    return {"run_id": run_id, "tab_id": run_id, "tier": tier, "engine": engine}


def _is_open(conn, run_id: str) -> bool:
    session = queries.get_session(conn, run_id)
    return session is not None and session["closed_at"] is None


def _watch(run, run_id: str, start_timeout: float) -> None:
    """Close the session when its tab never started, or has exited.

    Waits for whichever comes first, the host's "started" or a result: a tab that ended before
    it ever started (its result posted without a "started") is noticed at once, not when
    ``start_timeout`` runs out.
    """
    try:
        if not run.wait_started_or_result(start_timeout):
            close_chief(run_id, "never started")
            return
        run.wait_pty_result(None)
        close_chief(run_id, "tab closed")
    except Exception:
        logger.exception("chief watcher for %s failed", run_id)


def close_chief(run_id: str, reason: str) -> bool:
    """Close the session: revoke its token, remove its folder, drop its run.

    Returns False when the session was unknown or already closed, so it is safe to call twice.
    A watcher still waiting on the run is let go, so no thread outlives the session.
    """
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        return False
    try:
        return queries.close_session(get_db(), run_id, reason)
    finally:
        _remove_folder(run_id)
        run = get_run(run_id)
        if run is not None:
            run.mark_started()
            run.mark_pty_result({"closed": reason})
        drop_run(run_id)


LOCAL_ADDRESS = "127.0.0.1"


def _probe_address(host: str) -> str:
    """The address to connect to for a server that binds ``host``: this machine for a wildcard
    host (empty, or the unspecified IPv4 or IPv6 address), which names no one address.
    """
    try:
        wildcard = host == "" or ipaddress.ip_address(host).is_unspecified
    except ValueError:  # a host name, or not a string at all
        wildcard = False
    return LOCAL_ADDRESS if wildcard else host


def something_answers(host: str, port: int, timeout: float = 1.0) -> bool:
    """True when a TCP connection to ``host``:``port`` is accepted.

    A wildcard host is probed on 127.0.0.1. Any error, an unresolvable host or a port out of
    range included, means nothing answers.
    """
    try:
        with socket.create_connection((_probe_address(host), port), timeout=timeout):
            return True
    except (OSError, OverflowError, TypeError, ValueError):
        return False


def chief_startup_cleanup() -> list[str]:
    """Close every session the last server process left open and remove its folder.

    A chief open across a restart has no watcher left to close it, so its token and its hook
    secret must not outlive the process. Called once by ``app.main()`` before the server
    serves. Returns the closed run ids.
    """
    closed = queries.close_stale_sessions(get_db())
    for run_id in closed:
        if _RUN_ID_RE.fullmatch(run_id):
            _remove_folder(run_id)
    return closed
