"""Tests for the services layer. No fixture declarations needed — conftest._isolate_db is autouse."""


def test_get_flows_empty():
    from pathly_orchestrator.services import get_flows
    result = get_flows()
    assert isinstance(result, list)


def test_save_and_get_flow():
    from pathly_orchestrator.services import save_flow, get_flow
    save_flow({'name': 'test-flow', 'version': '1', 'flow_yaml': 'flow: test-flow'})
    result = get_flow('test-flow')
    assert result is not None
    assert result['name'] == 'test-flow'


def test_get_events_empty():
    from pathly_orchestrator.services import get_events
    result = get_events('/tmp/proj', 'my-feature')
    assert result == {'total': 0, 'events': []}


def test_get_spans_empty():
    from pathly_orchestrator.services import get_spans
    result = get_spans('/tmp/proj', 'my-feature')
    assert result == []


def test_get_agents_empty():
    from pathly_orchestrator.services import get_agents
    result = get_agents()
    assert isinstance(result, list)


def test_get_invocations_empty():
    from pathly_orchestrator.services import get_invocations
    result = get_invocations('/tmp/proj', 'my-feature')
    assert isinstance(result, list)


def test_get_skills_empty():
    from pathly_orchestrator.services import get_skills
    result = get_skills()
    assert isinstance(result, list)


def test_resolve_skill_missing():
    from pathly_orchestrator.services import resolve_skill
    result = resolve_skill('nonexistent-skill')
    assert result is None


def test_resolve_skill_local_first():
    from pathly_orchestrator.services import resolve_skill
    from pathly_orchestrator.db import get_db, upsert_skill_definition
    conn = get_db()
    upsert_skill_definition(conn, None, 'my-skill', 'my-skill.md', 'global', 'global content')
    upsert_skill_definition(conn, '/tmp/proj', 'my-skill', 'my-skill.md', 'local', 'local content')
    result = resolve_skill('my-skill', project_root='/tmp/proj')
    assert result['natural_language'] == 'local'


def test_get_artifacts_empty():
    from pathly_orchestrator.services import get_artifacts
    result = get_artifacts('/tmp/proj', 'my-feature')
    assert result == []
