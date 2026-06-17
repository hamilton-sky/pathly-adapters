"""Regression tests for PUT /skills/export — composition.yaml corruption guard.

The bug: a stray UI value (an absolute path to a plans artifact, e.g.
"C:/…/chat-automate-toggle/EDGE_CASES") was accepted as a `skill` and written into
the hand-maintained composition.yaml as a bogus key (and the round-trip stripped
all the manifest's doc comments). The route now rejects any non-skill-name key
BEFORE touching the file, so these tests never write to the real manifest.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_export_rejects_absolute_path_skill(client):
    """An absolute path masquerading as a skill name is rejected with 400."""
    bad = "C:/Users/Yafit/pathly-adapters/pathly/plans/chat-automate-toggle/EDGE_CASES"
    r = client.put("/skills/export", json={"skill": bad, "fragment_order": []})
    assert r.status_code == 400, r.data
    assert "skill" in json.loads(r.data)["error"].lower()


def test_export_rejects_backslash_skill(client):
    r = client.put("/skills/export", json={"skill": "a\\b\\c", "fragment_order": []})
    assert r.status_code == 400


def test_export_rejects_dotted_file_path(client):
    """A '<dir>/<file>.md' path is not a skill name — rejected."""
    r = client.put("/skills/export", json={"skill": "foo/bar.md", "fragment_order": []})
    assert r.status_code == 400


def test_export_rejects_leading_slash(client):
    r = client.put("/skills/export", json={"skill": "/team/build", "fragment_order": []})
    assert r.status_code == 400


def test_export_rejects_empty_skill(client):
    r = client.put("/skills/export", json={"skill": "  ", "fragment_order": []})
    assert r.status_code == 400


def test_export_rejects_non_string_fragment_order(client):
    """fragment_order must be a list of strings (defensive)."""
    r = client.put("/skills/export", json={"skill": "team/build", "fragment_order": [1, 2]})
    assert r.status_code == 400
