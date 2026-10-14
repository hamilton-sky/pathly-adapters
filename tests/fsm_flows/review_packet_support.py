"""Shared setup for the build-proof 10 tests (Review packet, review base, supervisor notes).

A real ``git init`` project, the packaged ``team-build`` flow, and helpers that drive a BUILDING
stage through ``next_action`` and ``complete_stage`` the way the supervisor does.
"""

from __future__ import annotations

import re
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest
import yaml

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task

FEATURE = "pathly/features/demo"
FROZEN = "Make x two. FROZEN-TASK-TEXT\n"
SUMMARY = "BUILDER-SAYS-ALL-GOOD"
DIFF_LINE = "x = 2  # LINE-FROM-THE-DIFF"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "src/app.py", "x = 1\ny = 2\n")
    _write(root, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    # build_prompt would otherwise start a code-intel tool through the `auto` backend.
    set_setting(get_db(), "code_context.backend", "off")
    return root


@pytest.fixture
def flow() -> dict:
    text = (
        files("pathly_data")
        .joinpath("core/flows/team-build.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _storage(repo: Path) -> Path:
    return repo / FEATURE


def _args(repo: Path) -> dict:
    return {
        "flow": "team-build",
        "topic": "demo",
        "project_root": str(repo),
        "scope": "demo",
    }


def _state(repo: Path) -> dict:
    return eventlog.read_state(str(_storage(repo))) or {}


def _enter_building(repo: Path, flow: dict) -> None:
    """Put the feature in BUILDING and let ``next_action`` stamp ``build_baseline``."""
    eventlog.write_state(str(_storage(repo)), {"current": "BUILDING"}, flow)
    fsm_ops.next_action(_args(repo))


def _claim(text: str = FROZEN) -> str:
    conn = get_db()
    task_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="planner",
        type="task",
        text=text,
    )
    assert claim_task(conn, task_id, "build")
    return task_id


def _build(repo: Path, flow: dict, edit: bool = True) -> str:
    """A BUILDING stage: baseline stamped, a task claimed, the builder edits and reports."""
    _enter_building(repo, flow)
    task_id = _claim()
    if edit:
        _write(repo, "src/app.py", "%s\ny = 2\n" % DIFF_LINE)
    eventlog.append_event(
        str(_storage(repo)),
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 1,
            "summary": SUMMARY,
            "outcome": "success",
        },
        flow=flow,
    )
    return task_id


def _packet(repo: Path) -> str:
    from pathly_orchestrator.fsm_compose_review import review_packet

    return review_packet(_storage(repo), str(repo), "feature", "demo", "")


def _section(packet: str, heading: str) -> str:
    found = re.search(
        r"^### %s\n(.*?)(?=^### |\Z)" % re.escape(heading), packet, re.S | re.M
    )
    assert found, "no '### %s' section in:\n%s" % (heading, packet[:2000])
    return found.group(1)


def _task_proof(repo: Path, task_id: str, checks: str, ts: str | None = None) -> None:
    event = {
        "type": "TASK_PROOF",
        "task_id": task_id,
        "claimed_at": "x",
        "run_id": "build",
        "checks": checks,
        "floor": "n/a",
        "warnings": [],
    }
    if ts is not None:
        event["ts"] = ts
    eventlog.append_event(str(_storage(repo)), event)
