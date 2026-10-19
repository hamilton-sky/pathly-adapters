"""chief-agent 08 (round 7): a key's declared kind fits what its view does with it.

A key of a plain kind (text, number, flag, enum, name, id) is opaque to the gate: it checks only
that the key is on the list. That is right only if the route never makes a path of it. The
audit (``test_chief_gate_audit.py``) finds a plain key that does by sending it hostile values;
this test finds the ones it can see in the source, so a change to a view is caught without a
hostile value having to land on it: a request key that a view or a helper under ``blueprints/``
reads and then passes, directly or through the names it is assigned to, to a call that makes or
opens a path (``chief_walk_support.keys_joined_into_paths``).

What it cannot see: a key handed to a function that joins it later (``start_run(flow=...)`` ends
in ``fsm_ops._load_flow``, ``start_board_run`` in ``_resolve_storage_path``), a call that is not
in its list of path calls, and a key read through a name it does not follow. Whether a file kind
is the *right* one (a folder name declared as a scope, a root declared as a path) is not judged
here either; the audit is the only check of that.
"""

from __future__ import annotations

from chief_gate_support import app
from chief_walk_support import keys_joined_into_paths, view_keys_joined_into_paths

# The plain keys a view joins into a path and holds before it does. ``(rule, method, key)`` ->
# what holds it. A line here is a claim about the view's code: the stale test below fails when
# the view stops joining the key, and the first test when a new key starts to.
HELD_BY_THE_VIEW = {
    ("/comms/run", "POST", "board"): (
        "any value that is not feature, project or global is replaced by feature first"
    ),
    ("/ops/export/skills", "GET", "adapter"): (
        "checked against the fixed list _VALID_ADAPTERS (400 otherwise) before the Path"
    ),
    ("/status", "GET", "topic"): (
        "_resolve_storage_path (_safe_topic) and an is_relative_to check on the resolved root"
    ),
}


def _joined_plain_keys(app) -> dict[tuple[str, str, str], set[str]]:
    from pathly_orchestrator.http_server.chief_field_types import FILE_KINDS
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    found: dict[tuple[str, str, str], set[str]] = {}
    for (rule, method), fields in sorted(ROUTE_FIELDS.items()):
        kinds = fields.kinds()
        for function, key, call in view_keys_joined_into_paths(app, rule, method):
            kind = kinds.get(key)
            if kind is not None and kind not in FILE_KINDS:
                found.setdefault((rule, method, key), set()).add(f"{function}: {call}")
    return found


def test_a_key_of_a_plain_kind_is_not_joined_into_a_path_unless_the_view_holds_it(app):
    unheld = {
        key: sorted(calls)
        for key, calls in _joined_plain_keys(app).items()
        if key not in HELD_BY_THE_VIEW
    }

    assert unheld == {}, (
        "a view makes a path of a key the table calls plain; give the key a kind with a rule "
        f"(root, scope, segment, path, ref, flow, skill) or say what holds it: {unheld}"
    )


def test_a_held_key_is_still_joined_into_a_path(app):
    """The detector is alive on the real views, and the list above cannot go stale."""
    found = set(_joined_plain_keys(app))

    stale = sorted(set(HELD_BY_THE_VIEW) - found)

    assert stale == [], f"the view no longer joins these keys into a path: {stale}"


# --- the detector, on source it is meant to understand -------------------------------------


def _joined(source: str, parameters: bool = False) -> set[str]:
    return {key for key, _call in keys_joined_into_paths(source, parameters)}


def test_a_key_that_reaches_a_join_through_a_name_is_seen():
    source = """
def view():
    data = read_json_body({})
    name = data.get("name")
    folder = str(name).strip()
    target = os.path.join(root, "pathly", folder)
    return target
"""
    assert _joined(source) == {"name"}


def test_a_key_read_by_subscript_or_a_query_string_is_seen():
    source = """
def view():
    leaf = request.args["leaf"]
    return open(f"{root}/{leaf}")
"""
    assert _joined(source) == {"leaf"}


def test_a_key_a_helper_takes_as_body_is_seen_only_for_a_helper():
    source = """
def helper(body):
    return Path(root) / body.get("sub")
"""
    assert _joined(source, parameters=True) == {"sub"}
    assert _joined(source, parameters=False) == set()


def test_a_string_method_is_not_a_path():
    source = """
def view():
    data = read_json_body({})
    text = data.get("text")
    clean = text.replace("a", "b")
    return ",".join([clean, str(text)])
"""
    assert _joined(source) == set()


def test_a_key_that_never_reaches_a_path_call_is_not_reported():
    source = """
def view():
    data = read_json_body({})
    name = data.get("name")
    os.path.join(root, "fixed")
    return lookup(name)
"""
    assert _joined(source) == set()
