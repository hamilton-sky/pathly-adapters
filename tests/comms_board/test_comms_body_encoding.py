"""Every comms POST route must read a non-UTF-8 request body.

Agents reach these routes through curl. On Windows a shell that is not in UTF-8 mode hands
curl a cp1252 body — one em-dash in an agent's prose is byte 0x97 — and Flask's
`request.get_json()` decodes strictly. `/comms/post` was hardened against exactly this, and
the fix was copy-pasted into `/comms/edit` and nowhere else. Measured across the whole
surface before `_helpers.read_json_body` existed:

  22 routes  -> 500, the write lost      (tasks/claim|complete|fail, goals/run, answer, ...)
  14 routes  -> body silently discarded, then "400: missing field" for a field that WAS sent

The sweep below is the real value here: it walks the live url_map, so a route added later is
covered without anyone remembering to add it to a list.
"""

from __future__ import annotations

import json

import pytest

from pathly_orchestrator.http_server.blueprints.comms._helpers import read_json_body


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _cp1252_body() -> bytes:
    return json.dumps(
        {
            "text": "did the thing — cleanly",
            "note": "reviewed — fine",
            "reason": "broke — badly",
            "query": "an em—dash",
        },
        ensure_ascii=False,
    ).encode("cp1252")


def _comms_post_paths(app) -> list[str]:
    paths = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
        path = str(rule)
        if not path.startswith("/comms") or "POST" not in rule.methods:
            continue
        paths.append(
            path.replace("<artifact_id>", "probe-id").replace(
                "<message_id>", "probe-id"
            )
        )
    return paths


def test_every_comms_post_route_reads_a_cp1252_body(client):
    """Sweeps the LIVE url_map, so a new route is covered automatically.

    A route "passes" when the body reaches its own logic — a 400 for a missing field or a
    404 for a bad id both prove that. It fails on a werkzeug BadRequest (body rejected) or a
    NameError/ImportError (the helper used but not imported — a wiring mistake that is easy
    to make when touching many files at once, and did happen while writing this).
    """
    from pathly_orchestrator.http_server import app

    body = _cp1252_body()
    rejected: list[str] = []
    crashed: list[str] = []
    for path in _comms_post_paths(app):
        payload = (
            client.post(path, data=body, content_type="application/json").get_json(
                silent=True
            )
            or {}
        )
        if payload.get("type") == "BadRequest":
            rejected.append(path)
        elif payload.get("type") in {"NameError", "ImportError", "AttributeError"}:
            crashed.append(f"{path}: {payload.get('error')}")

    assert not rejected, f"cp1252 body rejected by: {rejected}"
    assert not crashed, f"handler wiring broken: {crashed}"


def test_the_sweep_actually_covered_the_surface(client):
    """Guard the sweep from silently passing because it enumerated nothing."""
    from pathly_orchestrator.http_server import app

    paths = _comms_post_paths(app)
    assert len(paths) >= 30, f"only {len(paths)} comms POST routes found"
    for expected in ("/comms/post", "/comms/tasks/fail", "/comms/tasks/claim"):
        assert expected in paths


def test_task_fail_reason_is_the_case_that_bit(client):
    """The concrete regression: an agent's failure reason is free prose, and
    `team/build.md` sends it to this route on every unrecoverable task failure."""
    body = json.dumps(
        {"message_id": "no-such-task", "reason": "the build broke — badly"},
        ensure_ascii=False,
    ).encode("cp1252")
    r = client.post("/comms/tasks/fail", data=body, content_type="application/json")
    assert (r.get_json(silent=True) or {}).get("type") != "BadRequest"


# ── the helper itself ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_helper_decodes_both_encodings(client, encoding):
    from pathly_orchestrator.http_server import app

    payload = {"text": "smart — quote"}
    with app.test_request_context(
        "/x",
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode(encoding),
    ):
        assert read_json_body() == payload


@pytest.mark.parametrize(
    "raw,default,expected",
    [
        (b"", None, None),
        (b"", {}, {}),
        (b"not json at all", None, None),
        (b"[1, 2, 3]", None, None),  # a JSON array is not a body these routes accept
        (b"[1, 2, 3]", {}, {}),
    ],
)
def test_helper_falls_back_to_its_default(client, raw, default, expected):
    """Each caller keeps the contract it already had: None for the routes that 400 on a bad
    body, {} for the ones that fall through to their own defaults."""
    from pathly_orchestrator.http_server import app

    with app.test_request_context("/x", method="POST", data=raw):
        assert read_json_body(default) == expected


def test_helper_ignores_a_missing_content_type(client):
    """Deliberate: an agent's curl that omits the JSON header is still understood. This is
    what /comms/post has always done, and it is why the helper reads get_data()."""
    from pathly_orchestrator.http_server import app

    with app.test_request_context(
        "/x", method="POST", data=b'{"text": "hi"}', content_type="text/plain"
    ):
        assert read_json_body() == {"text": "hi"}
