from pathlib import Path

from flask import Blueprint, request, jsonify
from pathly_orchestrator.services import (
    get_feature_list, get_events, get_invocations, get_event_count, get_spans,
    get_artifacts, get_flows, save_flow, get_skills, get_agents,
    record_skill_override,
)

api_bp = Blueprint('api', __name__, url_prefix='')


@api_bp.route('/api/features', methods=['GET'])
def api_features():
    project_root = request.args.get('project_root')
    if not project_root:
        return jsonify([]), 200
    result = get_feature_list(project_root)
    return jsonify(result), 200


@api_bp.route('/api/features/<feature>/events', methods=['GET'])
def api_feature_events(feature):
    project_root = request.args.get('project_root', '')
    since_seq = int(request.args.get('since_seq', 0))
    result = get_events(project_root, feature, since_seq)
    return jsonify(result), 200


@api_bp.route('/api/features/<feature>/invocations', methods=['GET'])
def api_feature_invocations(feature):
    project_root = request.args.get('project_root', '')
    result = get_invocations(project_root, feature)
    return jsonify(result), 200


@api_bp.route('/api/features/<feature>/metrics', methods=['GET'])
def api_feature_metrics(feature):
    project_root = request.args.get('project_root', '')
    event_count = get_event_count(project_root, feature)
    invocations = get_invocations(project_root, feature)
    spans = get_spans(project_root, feature)
    return jsonify({
        'event_count': event_count,
        'invocation_count': len(invocations),
        'span_count': len(spans),
    }), 200


@api_bp.route('/api/features/<feature>/artifacts', methods=['GET'])
def api_feature_artifacts(feature):
    project_root = request.args.get('project_root', '')
    result = get_artifacts(project_root, feature)
    return jsonify(result), 200


@api_bp.route('/api/flows', methods=['GET'])
def api_flows():
    project_root = request.args.get('project_root')
    result = get_flows(project_root)
    return jsonify(result), 200


@api_bp.route('/api/flows', methods=['POST'])
def api_flows_post():
    body = request.get_json(force=True) or {}
    if not body.get('name'):
        return jsonify({'error': 'name required'}), 400
    save_flow(body)
    return jsonify({'ok': True}), 200


@api_bp.route('/api/skills', methods=['GET'])
def api_skills():
    project_root = request.args.get('project_root')
    result = get_skills(project_root)
    return jsonify(result), 200


@api_bp.route('/api/agents', methods=['GET'])
def api_agents():
    project_root = request.args.get('project_root')
    result = get_agents(project_root)
    return jsonify(result), 200


@api_bp.route('/api/traces', methods=['GET'])
def api_traces():
    project_root = request.args.get('project_root', '')
    feature = request.args.get('feature', '')
    run_id = request.args.get('run_id')
    result = get_spans(project_root, feature, run_id)
    return jsonify(result), 200


@api_bp.route('/api/skill-override', methods=['POST'])
def api_skill_override():
    body = request.get_json(force=True) or {}
    required = ['project_root', 'feature', 'stage', 'skill_name']
    for field in required:
        if not body.get(field):
            return jsonify({'error': f'{field} required'}), 400
    record_skill_override(
        body['project_root'],
        body['feature'],
        body.get('run_id'),
        body['stage'],
        body['skill_name'],
    )
    return jsonify({'ok': True}), 200


@api_bp.route('/api/project/open', methods=['POST'])
def project_open():
    body = request.get_json(force=True) or {}
    project_root = body.get('project_root', '')
    features = []
    plans_dir = Path(project_root) / 'pathly' / 'plans'
    if plans_dir.exists():
        for entry in sorted(plans_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                features.append(entry.name)
    return jsonify({'features': features}), 200
