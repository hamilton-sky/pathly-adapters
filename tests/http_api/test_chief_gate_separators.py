"""chief-agent 08 (round 7): the gate reads "the same directory" the way the host does.

The routes use a request's ``project_root`` as the raw string: ``os.path.join(root, "pathly", ...)``,
``os.makedirs``, a git working directory. On a POSIX host a backslash is an ordinary file-name
character, so ``/work/proj\\`` is a sibling folder of ``/work/proj`` and ``\\work\\proj`` is a
relative path under the server's working directory. The gate used to turn ``\\`` into ``/`` before
it compared, so both passed as the chief's own root. ``scope_names.host_is_windows`` is now the one
place that says which reading applies, and these tests switch it: the server-backed tests send the
spellings through the real routes on this (POSIX) host and watch the file system; the unit tests
try both readings, so the Windows one stays covered on any host.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest
from chief_audit_sandbox import drain_the_mirrors, world
from chief_audit_world import settle
from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)
from werkzeug.datastructures import MultiDict

OWN = "/tmp/chief-separators/proj-a"
SESSION = {"project_root": OWN}


def _host(monkeypatch, windows: bool) -> None:
    """Make the gate read separators as the given kind of host does (``raising=False`` only so
    that the tests fail for the behaviour, not for the missing switch, before the fix).
    """
    monkeypatch.setattr(
        "pathly_orchestrator.scope_names.host_is_windows",
        lambda: windows,
        raising=False,
    )


def _backslashed(project) -> dict[str, str]:
    """Spellings of the chief's root that a backslash-as-separator reading takes for its own."""
    own = str(project)
    return {
        "a backslash at the end": own + "\\",
        "backslashes for every slash": own.replace("/", "\\"),
        "a backslash before the folder": f"{project.parent}\\{project.name}",
        "a climb with backslashes": f"{own}/sub\\..\\..\\{project.name}",
    }


def _same_directory(project) -> dict[str, str]:
    """Spellings that name the chief's root on a POSIX host, or that the gate should not take
    for it: whatever it decides, nothing may land outside the project.
    """
    own = str(project)
    return {
        "a slash at the end": own + "/",
        "two slashes at the end": own + "//",
        "a dot segment at the end": own + "/.",
        "a dot segment in the middle": own.replace(project.name, "./" + project.name),
        "doubled slashes": own.replace("/", "//"),
        "padded": f" {own}",
    }


ROUTES = [
    ("planner", "/comms/features/decompose"),
    ("planner", "/comms/goals/decompose"),
    ("planner", "/comms/project/decompose"),
    ("operator", "/comms/features/decompose"),
    ("operator", "/comms/goals/decompose"),
    ("operator", "/comms/project/decompose"),
    ("operator", "/comms/goals/run"),
    ("operator", "/comms/run"),
    ("operator", "/code/query"),
]


def _send_all(env, tier: str, rule: str, root: str):
    """Send every valid request of ``rule`` with ``root`` as its ``project_root``."""
    w = env.world
    chief = _chief(tier, w.project)
    answers = []
    for variant in w.variants(rule, "POST"):
        answers.append(
            w.request(rule, "POST", variant, "project_root", root, chief.headers)
        )
        settle()
    drain_the_mirrors()
    return answers


def _planted(env) -> list[str]:
    """What a request left where the chief's project is not: anything in the server's working
    directory, and any file or folder, anywhere under the home, whose name has a backslash.
    """
    w = env.world
    mark = (len(env.audit.violations), len(env.audit.seen))
    found = [p.name for p in w.server.iterdir()]
    found += [str(p) for p in w.project.parent.rglob("*") if "\\" in p.name]
    # The listing above is the test's own, not the server's: the audit must not count it.
    del env.audit.violations[mark[0] :], env.audit.seen[mark[1] :]
    return found


@pytest.mark.parametrize("tier,rule", ROUTES)
@pytest.mark.parametrize("spelling", list(_backslashed(PurePosixPath("/a/proj"))))
def test_a_backslash_spelling_of_the_chiefs_root_is_refused_and_plants_nothing(
    world, monkeypatch, tier, rule, spelling
):
    _host(monkeypatch, windows=False)
    root = _backslashed(world.world.project)[spelling]

    answers = _send_all(world, tier, rule, root)

    assert all(_gated(a) for a in answers), [
        (a.status_code, a.get_data(as_text=True)[:100]) for a in answers
    ]
    assert _planted(world) == []
    assert world.audit.violations == [], world.audit.violations[:5]


@pytest.mark.parametrize("tier,rule", ROUTES)
@pytest.mark.parametrize("spelling", list(_same_directory(PurePosixPath("/a/proj"))))
def test_no_other_spelling_of_the_chiefs_root_lands_outside_it(
    world, monkeypatch, tier, rule, spelling
):
    _host(monkeypatch, windows=False)
    root = _same_directory(world.world.project)[spelling]

    _send_all(world, tier, rule, root)

    assert _planted(world) == []
    assert world.audit.violations == [], world.audit.violations[:5]


@pytest.mark.parametrize("tier,rule", ROUTES)
@pytest.mark.parametrize("spelling", ["a slash at the end", "two slashes at the end"])
def test_a_trailing_slash_is_the_same_directory_and_the_route_runs(
    world, monkeypatch, tier, rule, spelling
):
    _host(monkeypatch, windows=False)
    root = _same_directory(world.world.project)[spelling]

    answers = _send_all(world, tier, rule, root)

    assert all(_passed(a) for a in answers), [
        (a.status_code, a.get_data(as_text=True)[:100]) for a in answers
    ]
    assert world.audit.violations == [], world.audit.violations[:5]


# --- the gate's own decision, on both readings of a backslash ---------------------------------


def _refusal(body: dict, windows: bool, monkeypatch, rule="/comms/search"):
    from pathly_orchestrator.http_server.chief_project import project_refusal

    _host(monkeypatch, windows)
    return project_refusal(rule, "POST", SESSION, body, MultiDict())


@pytest.mark.parametrize(
    "root",
    [
        OWN + "\\",
        OWN.replace("/", "\\"),
        "/tmp/chief-separators\\proj-a",
        OWN + "/",
    ],
    ids=["end", "all", "mixed", "slash"],
)
def test_a_root_with_a_backslash_is_the_chiefs_own_on_windows_only(root, monkeypatch):
    body = {"query": "", "feature": "demo", "project_root": root}

    on_windows = _refusal(body, True, monkeypatch)
    on_posix = _refusal(body, False, monkeypatch)

    assert on_windows is None
    assert (on_posix is None) == root.endswith("/"), on_posix


@pytest.mark.parametrize("scope", [OWN + "\\", OWN.replace("/", "\\")])
def test_a_project_board_scope_with_a_backslash_follows_the_host(scope, monkeypatch):
    body = {"feature": "demo", "board": "project", "scope": scope}

    assert _refusal(body, True, monkeypatch) is None
    assert _refusal(body, False, monkeypatch) is not None


@pytest.mark.parametrize(
    "path,inside_on_windows",
    [
        (OWN + "\\src\\x.py", True),
        (OWN.replace("/", "\\") + "\\x.py", True),
        (OWN + "/src\\x.py", True),
        (OWN + "\\..\\proj-b\\x.py", False),
        (OWN + "\\src\\..\\..\\other\\x.py", False),
        (OWN + "/src/x.py", True),
        (OWN + "/../proj-b/x.py", False),
    ],
)
def test_a_path_with_a_backslash_is_read_as_a_path_on_windows_only(
    path, inside_on_windows, monkeypatch
):
    """``/code/query`` ``target`` and the ``artifact_path`` of a post: the routes open the raw
    string, so on a POSIX host a path with a backslash is a different file, and is refused.
    """
    for rule, key in (("/code/query", "target"), ("/comms/post", "artifact_path")):
        body = {key: path, "project_root": OWN}
        if rule == "/comms/post":
            body["from"] = "chief"
        windows = _refusal(body, True, monkeypatch, rule)
        posix = _refusal(body, False, monkeypatch, rule)

        assert (windows is None) == inside_on_windows, (rule, windows)
        if "\\" in path:
            assert posix is not None, (rule, path)
        else:
            assert posix == windows, (rule, path, posix, windows)


def test_a_session_root_with_a_backslash_on_a_posix_host_binds_nothing(monkeypatch):
    """A directory whose name has a backslash cannot be told apart from the spelling that turns
    the backslash into a slash, so a chief opened on one has no root the gate can match.
    """
    from pathly_orchestrator.http_server.chief_project import project_refusal

    _host(monkeypatch, False)
    session = {"project_root": "/tmp/chief-separators/odd\\name"}
    for root in ("/tmp/chief-separators/odd\\name", "/tmp/chief-separators/odd/name"):
        body = {"query": "", "feature": "demo", "project_root": root}
        assert project_refusal("/comms/search", "POST", session, body, MultiDict())
