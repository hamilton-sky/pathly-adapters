"""chief-agent 08 (round 6): the key list of every route, read against the code.

``ROUTE_FIELDS`` is the complete list of the keys a chief may send to a route. These tests read
the table and the source of the views (and of the helpers under ``blueprints/`` they call), by
what each name is bound to (``chief_walk_support``), not by what the key is called:

* every key a view or helper reads from the request is listed, or is in ``not_for_chief``;
* every ``not_for_chief`` key is in fact read (the list of deliberate omissions cannot go stale);
* every key an entry lists is read by the route, is a URL variable, or waits for a later ticket;
* every key that can reach a file or a folder has a kind, and for each kind the gate refuses
  hostile values.

What they cannot see: a key read by a function outside ``blueprints/`` that is handed the whole
body, or by a view that reads the body through a name the walk does not follow. The audit test
(``test_chief_gate_audit.py``) covers the other direction: it sends hostile values and watches
what the server touches.
"""

from __future__ import annotations

import pytest
from chief_gate_support import app
from chief_walk_support import view_keys_read
from werkzeug.datastructures import MultiDict

# Keys a later ticket reads and no view reads yet: listing one here lets the entry carry it ahead
# of the view. Empty since ticket 15 made `POST /runs` read `max_cost_usd`.
WAITS_FOR_A_TICKET: set[tuple[str, str]] = set()
# Keys the chief gate reads and no view does: the cite rule (`chief_cite`, ticket 10) reads `cite`
# on the three answer routes to find the message a chief relays.
READ_BY_THE_GATE = {
    ("/comms/acknowledge", "cite"),
    ("/comms/answer", "cite"),
    ("/runner/agent-answer", "cite"),
}
OWN = "/tmp/chief-keys/proj-a"


@pytest.fixture(autouse=True)
def _posix_host(monkeypatch):
    """The roots below are POSIX paths: read separators the way a POSIX host does, wherever the
    suite runs (a backslash is then a file-name character, not a separator).
    """
    monkeypatch.setattr(
        "pathly_orchestrator.scope_names.host_is_windows",
        lambda: False,
        raising=False,
    )


def _entries():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    return sorted(ROUTE_FIELDS.items())


def test_every_key_has_a_kind_the_gate_knows():
    from pathly_orchestrator.http_server.chief_field_types import KINDS

    unknown = {
        (key, name): kind
        for key, fields in _entries()
        for name, kind in fields.kinds().items()
        if kind not in KINDS
    }

    assert unknown == {}


def test_no_key_is_both_listed_and_deliberately_absent():
    both = {
        key: sorted(set(fields.not_for_chief) & set(fields.kinds()))
        for key, fields in _entries()
        if set(fields.not_for_chief) & set(fields.kinds())
    }

    assert both == {}


def test_a_key_a_view_reads_is_listed_or_deliberately_absent(app):
    forgotten = {}
    for (rule, method), fields in _entries():
        read = view_keys_read(app, rule, method)
        every = set().union(*read.values()) if read else set()
        missing = every - fields.allowed(rule) - set(fields.not_for_chief)
        if missing:
            forgotten[(rule, method)] = sorted(missing)

    assert forgotten == {}, (
        "a view reads request keys the entry neither lists nor puts in not_for_chief "
        f"(a chief could send them): {forgotten}"
    )


def test_a_key_left_out_on_purpose_is_one_a_view_reads(app):
    stale = {}
    for (rule, method), fields in _entries():
        read = view_keys_read(app, rule, method)
        every = set().union(*read.values()) if read else set()
        gone = set(fields.not_for_chief) - every
        if gone:
            stale[(rule, method)] = sorted(gone)

    assert stale == {}, f"not_for_chief names keys no view reads: {stale}"


def test_a_listed_key_is_read_or_is_a_url_variable_or_waits_for_a_ticket(app):
    from pathly_orchestrator.http_server.chief_field_types import url_variables

    unread = {}
    for (rule, method), fields in _entries():
        read = view_keys_read(app, rule, method)
        every = set().union(*read.values()) if read else set()
        wasted = {
            name
            for name in fields.kinds()
            if name not in every
            and name not in url_variables(rule)
            and (rule, name) not in WAITS_FOR_A_TICKET | READ_BY_THE_GATE
        }
        if wasted:
            unread[(rule, method)] = sorted(wasted)

    assert unread == {}, f"a chief may send keys no route reads: {unread}"


def test_a_key_that_waits_for_a_ticket_is_listed_or_refused_naming_it():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS
    from pathly_orchestrator.http_server.chief_keys import key_refusal

    for rule, key in sorted(WAITS_FOR_A_TICKET | READ_BY_THE_GATE):
        fields = ROUTE_FIELDS[(rule, "POST")]
        refusal = key_refusal(rule, "POST", {key: 1})

        if key in fields.allowed(rule):
            assert refusal is None, (rule, key)
        else:
            assert refusal is not None and repr(key) in refusal, (rule, key)


def test_the_keys_the_gate_reads_are_the_ones_the_cite_rule_reads():
    from pathly_orchestrator.http_server.chief_cite import TARGET_KEYS

    assert READ_BY_THE_GATE == {(rule, "cite") for rule in TARGET_KEYS}


def test_a_key_that_waits_for_a_ticket_is_taken_off_the_list_when_a_view_reads_it(app):
    """The list says what no view reads yet. The ticket that reads a key deletes its line (and,
    for an unlisted key, lists it); this fails until it does.
    """
    read_already = [
        (rule, key)
        for rule, key in sorted(WAITS_FOR_A_TICKET)
        if any(key in keys for keys in view_keys_read(app, rule, "POST").values())
    ]

    assert (
        read_already == []
    ), f"delete these lines of WAITS_FOR_A_TICKET: {read_already}"


def test_the_walk_sees_the_keys_it_is_meant_to_see(app):
    """Pins the reader: a flow, a skill and the keys of a helper are seen like a scope is."""
    run = view_keys_read(app, "/comms/goals/run", "POST")
    skill = view_keys_read(app, "/comms/run", "POST")
    flow = view_keys_read(app, "/runs", "POST")
    section = view_keys_read(app, "/comms/artifacts/<artifact_id>/section", "GET")

    assert {"flow", "ability_ids", "executor"} <= run["comms_goals_run"]
    assert {"skill", "system_prompt", "interactive"} <= skill["comms_run"]
    assert "flow" in flow["_create_flow_run"]
    assert {"artifact", "anchor", "trail"} <= section["comms_artifact_section"]


def test_a_url_variable_is_not_a_key():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS
    from pathly_orchestrator.http_server.chief_keys import key_refusal

    assert "run_id" in ROUTE_FIELDS[("/runs/<run_id>", "GET")].kinds()
    assert "run_id" not in ROUTE_FIELDS[("/runs/<run_id>", "GET")].allowed(
        "/runs/<run_id>"
    )
    assert key_refusal("/runs/<run_id>", "GET", {"run_id": "x"}) is not None
    assert key_refusal("/runs/<run_id>", "GET", {"project_root": OWN}) is None
    assert key_refusal("/runs/<run_id>/stop", "POST", {"run_id": "x"}) is not None


def test_a_key_that_is_not_listed_is_refused_naming_it():
    from pathly_orchestrator.http_server.chief_keys import key_refusal

    reason = key_refusal("/comms/goals/run", "POST", {"goal_id": "g", "zz": 1})

    assert reason is not None and "'zz'" in reason
    assert key_refusal("/comms/goals/run", "POST", {"goal_id": "g"}) is None
    assert key_refusal("/comms", "GET", MultiDict([("limit", "3"), ("zz", "1")]))


def test_a_repeated_query_key_is_one_key():
    from pathly_orchestrator.http_server.chief_keys import key_refusal

    assert (
        key_refusal("/comms", "GET", MultiDict([("limit", "1"), ("limit", "2")]))
        is None
    )
    assert (
        key_refusal("/comms", "GET", MultiDict([("zz", "1"), ("zz", "2")])) is not None
    )


# --- each kind that can reach a file or a folder has a rule, applied to hostile values -----

HOSTILE_NAMES = [
    "..",
    "../x",
    "../../x",
    "a/../x",
    "/abs/x",
    "//server/share/x",
    "C:/x",
    "C:\\x",
    "x\\y",
    "x/",
    "a/b",
    "x\0y",
    ".",
    "/",
    "x:y",
    "x" * 5000 + "/..",
]
# The chief's own root spelled so that a reading of backslash as a separator takes it for the
# chief's own. The routes open the raw string, where it is a file-name character.
BACKSLASHED_ROOTS = [
    OWN + "\\",
    OWN.replace("/", "\\"),
    "/tmp/chief-keys\\proj-a",
    OWN + "/sub\\..\\..\\proj-b",
]
HOSTILE_PATHS = [
    "../../etc/passwd",
    "/tmp/chief-keys/proj-b/x",
    "/tmp/chief-keys/proj-a/../proj-b/x",
    "/tmp/chief-keys/proj-a-evil/x",
    "//server/share/x",
    "C:/x",
    "C:\\Windows\\x",
    "/etc/passwd",
    "x\0y/../../proj-b",
    OWN + "\\x.py",
    OWN.replace("/", "\\") + "\\x.py",
    OWN + "/src\\..\\..\\proj-b\\x.py",
]
SESSION = {"project_root": OWN}


def _sources(fields, name: str, value) -> list:
    """The request sources that carry ``name`` = ``value``, one per board a scope can be on."""
    for read in fields.scopes:
        if name in read.keys:
            if read.board_key:
                return [
                    {name: value, read.board_key: board}
                    for board in ("feature", "project", "global")
                ]
            return [{name: value}]
    return [{name: value}]


def _refused(rule, method, fields, source, view_args=None, names_root=True) -> bool:
    """True when the gate refuses ``source`` for ``rule``. A route that reads a root is given the
    chief's own (``names_root``), so a refusal is for the key under test, not for a missing root.
    """
    from pathly_orchestrator.http_server.chief_project import project_refusal

    if names_root and "project_root" in fields.roots and "project_root" not in source:
        source = {**source, "project_root": OWN}
    body = {} if method == "GET" else source
    args = MultiDict(source) if method == "GET" else MultiDict()
    if project_refusal(rule, method, SESSION, body, args, view_args or {}) is not None:
        return True
    from pathly_orchestrator.http_server.chief_keys import key_refusal

    return key_refusal(rule, method, args if method == "GET" else body) is not None


def _keys_of_kind(*kinds):
    return [
        pytest.param(rule, method, name, kind, id=f"{method} {rule} {name}")
        for (rule, method), fields in _entries()
        for name, kind in fields.kinds().items()
        if kind in kinds
    ]


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("scope", "segment"))
def test_a_scope_that_is_not_the_chiefs_root_or_one_folder_name_is_refused(
    rule, method, name, kind
):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    for value in [*HOSTILE_NAMES, *BACKSLASHED_ROOTS, "/tmp/chief-keys/proj-b"]:
        for source in _sources(fields, name, value):
            assert _refused(rule, method, fields, source), (value, source)


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("segment"))
def test_a_segment_refuses_the_chiefs_own_root_too(rule, method, name, kind):
    """A key the server makes a folder of is one folder name even when it is the chief's root.

    A ``segments`` field (a goal's slug) is a segment on every board; a ``segment`` scope is one
    off the project board, where the scope is the root and a folder is made of nothing.
    """
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    for source in _sources(fields, name, OWN):
        if "project" in source.values():
            continue
        assert _refused(rule, method, fields, source), source


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("path"))
def test_a_path_outside_the_chiefs_project_is_refused(rule, method, name, kind):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    for value in HOSTILE_PATHS:
        assert _refused(rule, method, fields, {name: value}), value


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("flow", "skill"))
def test_a_flow_or_a_skill_that_is_not_one_name_is_refused(rule, method, name, kind):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    hostile = (
        HOSTILE_NAMES if kind == "flow" else [v for v in HOSTILE_NAMES if v != "a/b"]
    )
    for value in hostile:
        assert _refused(rule, method, fields, {name: value}), value
    good = "team-build" if kind == "flow" else "planning/evaluate"
    assert not _refused(rule, method, fields, {name: good})


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("root"))
def test_a_root_that_is_not_the_chiefs_is_refused(rule, method, name, kind):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    for value in [
        "/tmp/chief-keys/proj-b",
        "proj/x",
        "..",
        "../proj-a",
        "//server/share",
        "C:\\x",
        "x\0",
        ["a"],
        {"a": 1},
        7,
        *BACKSLASHED_ROOTS,
    ]:
        assert _refused(
            rule, method, fields, {name: value}, {"action": "retry"}, names_root=False
        ), value


@pytest.mark.parametrize("rule,method,name,kind", _keys_of_kind("ref"))
def test_a_file_ref_is_read_under_a_root_the_request_names(rule, method, name, kind):
    """A ``ref`` is resolved by the sink under the root the request names
    (``hydrate.safe_artifact_path``), so the gate makes the call name one: the root is required
    whenever the ref is sent, and a foreign root is refused.
    """
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    fields = ROUTE_FIELDS[(rule, method)]
    assert "project_root" in fields.roots, (rule, name)
    assert fields.names_root or name in fields.names_root_when, (rule, name)
    source = {name: "pathly/features/x/PLAN.md"}
    assert _refused(
        rule, method, fields, source, names_root=False
    ), "a ref with no root must be refused"
    assert not _refused(
        rule, method, fields, {**source, "project_root": OWN}
    ), "a ref under the chief's own root is let through"
    assert _refused(rule, method, fields, {**source, "project_root": OWN + "-b"})
