"""Tests for the HTTP routes Blueprint (api/__init__.py). Uses Flask test client."""
from __future__ import annotations

import json
import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app, _rate_counters
    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- S4.1: Catalog GET endpoints return 200 + JSON array ---

def test_get_flows_returns_200(client):
    r = client.get('/api/flows')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


def test_get_skills_returns_200(client):
    r = client.get('/api/skills')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


def test_get_agents_returns_200(client):
    r = client.get('/api/agents')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


def test_get_traces_returns_200(client):
    r = client.get('/api/traces?project_root=/tmp/p&feature=f')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)


# --- S4.1: Feature sub-routes ---

def test_get_features_no_project_root_returns_empty(client):
    r = client.get('/api/features')
    assert r.status_code == 200
    assert json.loads(r.data) == []


def test_get_feature_events_returns_200(client):
    r = client.get('/api/features/my-feature/events?project_root=/tmp/p')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert 'total' in data
    assert 'events' in data


def test_get_feature_invocations_returns_200(client):
    r = client.get('/api/features/my-feature/invocations?project_root=/tmp/p')
    assert r.status_code == 200
    assert isinstance(json.loads(r.data), list)


def test_get_feature_metrics_returns_200(client):
    r = client.get('/api/features/my-feature/metrics?project_root=/tmp/p')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert 'event_count' in data
    assert 'invocation_count' in data
    assert 'span_count' in data


def test_get_feature_artifacts_returns_200(client):
    r = client.get('/api/features/my-feature/artifacts?project_root=/tmp/p')
    assert r.status_code == 200
    assert isinstance(json.loads(r.data), list)


# --- S4.2: project/open ---

def test_project_open_missing_dir_returns_empty(client):
    r = client.post(
        '/api/project/open',
        data=json.dumps({'project_root': '/nonexistent/path/xyz'}),
        content_type='application/json',
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data == {'features': []}


def test_project_open_with_plans_dir(client, tmp_path):
    plans_dir = tmp_path / 'pathly' / 'plans'
    plans_dir.mkdir(parents=True)
    (plans_dir / 'feature-a').mkdir()
    (plans_dir / 'feature-b').mkdir()
    (plans_dir / '.archive').mkdir()  # hidden — should be excluded
    r = client.post(
        '/api/project/open',
        data=json.dumps({'project_root': str(tmp_path)}),
        content_type='application/json',
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert set(data['features']) == {'feature-a', 'feature-b'}


# --- S4.2: skill-override validation ---

def test_skill_override_missing_fields_returns_400(client):
    r = client.post(
        '/api/skill-override',
        data=json.dumps({'project_root': '/tmp/p'}),
        content_type='application/json',
    )
    assert r.status_code == 400
    data = json.loads(r.data)
    assert 'error' in data


def test_skill_override_valid_returns_200(client):
    r = client.post(
        '/api/skill-override',
        data=json.dumps({
            'project_root': '/tmp/p',
            'feature': 'my-feature',
            'run_id': 'abc123',
            'stage': 'BUILD',
            'skill_name': 'pathly-build',
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    assert json.loads(r.data) == {'ok': True}


# --- POST /api/flows ---

def test_post_flows_missing_name_returns_400(client):
    r = client.post(
        '/api/flows',
        data=json.dumps({'flow_yaml': 'flow: test'}),
        content_type='application/json',
    )
    assert r.status_code == 400


def test_post_flows_valid_returns_200(client):
    r = client.post(
        '/api/flows',
        data=json.dumps({'name': 'test-flow', 'flow_yaml': 'flow: test-flow'}),
        content_type='application/json',
    )
    assert r.status_code == 200
    assert json.loads(r.data) == {'ok': True}
