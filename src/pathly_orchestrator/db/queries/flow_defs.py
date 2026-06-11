"""Query helpers for the flow_definitions table."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

import yaml

from ..connection import _get_write_lock

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers — no DB access
# ---------------------------------------------------------------------------

def _decompose_flow_dict(flow_dict: dict) -> tuple[dict, list[dict], list[dict]]:
    """Split a parsed YAML flow dict into (flow_level_config, node_rows, edge_rows).

    Returns:
        flow_level_config  — dict with keys: version, flow, storage_path,
                             feedback_routing, scope_gate, adapter_default, _comments
        node_rows          — list of dicts with keys: node_id, node_type, agent, role,
                             adapter, skill, is_terminal, position, config_json (JSON str or None)
        edge_rows          — list of dicts with keys: source_node, target_node, ordinal,
                             config_json (JSON str or None)
    """
    adapter_map = flow_dict.get("adapter_map") or {}
    transitions = flow_dict.get("transitions") or {}
    agent_map = flow_dict.get("agent_map") or {}
    role_map = flow_dict.get("role_map") or {}
    skill_map = flow_dict.get("skill_map") or {}
    transition_rules = flow_dict.get("transition_rules") or {}
    composition = flow_dict.get("composition") or {}
    transition_actions = flow_dict.get("transition_actions") or {}
    gates = flow_dict.get("gates") or {}

    flow_level_config: dict = {}
    for key in ("version", "flow", "storage_path", "feedback_routing", "scope_gate", "_comments"):
        val = flow_dict.get(key)
        if val is not None:
            flow_level_config[key] = val
    adapter_default = adapter_map.get("default")
    if adapter_default is not None:
        flow_level_config["adapter_default"] = adapter_default

    states = flow_dict.get("states") or []
    node_rows: list[dict] = []
    for position, state in enumerate(states):
        state_transitions = transitions.get(state)
        is_terminal = 1 if state_transitions == [] else 0

        node_cfg: dict = {}
        rule = transition_rules.get(state)
        if rule is not None:
            node_cfg["transition_rule"] = rule
        comp_block = composition.get(state)
        if comp_block is not None:
            node_cfg["composition_block"] = comp_block

        per_state_adapter = adapter_map.get(state)

        node_rows.append({
            "node_id": state,
            "node_type": "state",
            "position": position,
            "agent": agent_map.get(state),
            "role": role_map.get(state),
            "adapter": per_state_adapter,
            "skill": skill_map.get(state),
            "is_terminal": is_terminal,
            "config_json": json.dumps(node_cfg, ensure_ascii=False) if node_cfg else None,
        })

    edge_rows: list[dict] = []
    for state in states:
        targets = transitions.get(state)
        if not targets:
            continue
        for ordinal, target in enumerate(targets):
            edge_cfg: dict = {}
            edge_key = f"{state}->{target}"
            actions = transition_actions.get(edge_key)
            if actions is not None:
                edge_cfg["actions"] = actions
            edge_gates = gates.get(edge_key)
            if edge_gates is not None:
                edge_cfg["gates"] = edge_gates
            edge_rows.append({
                "source_node": state,
                "target_node": target,
                "ordinal": ordinal,
                "config_json": json.dumps(edge_cfg, ensure_ascii=False) if edge_cfg else None,
            })

    return flow_level_config, node_rows, edge_rows


def _assemble_from_parts(
    flow_level_config: dict,
    node_rows: list[dict],
    edge_rows: list[dict],
) -> dict:
    """Pure inverse of _decompose_flow_dict. Uses in-memory row lists.
    Used by the round-trip test in Phase 1 and called by _assemble_flow_dict in Phase 2."""
    result: dict = {}

    # Scalar flow-level fields
    for key in ("version", "flow", "storage_path"):
        if key in flow_level_config:
            result[key] = flow_level_config[key]

    # states: ordered by position
    sorted_nodes = sorted(node_rows, key=lambda r: r["position"])
    result["states"] = [r["node_id"] for r in sorted_nodes]

    # transitions: group edge_rows by source_node, ordered by ordinal.
    # Only include states that either have outgoing edges OR were explicitly terminal
    # (is_terminal==1 means transitions[state]=[] in the original YAML).
    # States absent from original transitions (is_terminal==0, no edges) are omitted.
    edge_by_source: dict[str, list] = {}
    for edge in edge_rows:
        src = edge["source_node"]
        if src not in edge_by_source:
            edge_by_source[src] = []
        edge_by_source[src].append(edge)

    transitions: dict = {}
    for node in sorted_nodes:
        nid = node["node_id"]
        if nid in edge_by_source:
            sorted_edges = sorted(edge_by_source[nid], key=lambda e: e["ordinal"])
            transitions[nid] = [e["target_node"] for e in sorted_edges]
        elif node.get("is_terminal"):
            transitions[nid] = []
    result["transitions"] = transitions

    # agent_map
    agent_map = {r["node_id"]: r["agent"] for r in sorted_nodes if r.get("agent")}
    if agent_map:
        result["agent_map"] = agent_map

    # role_map
    role_map = {r["node_id"]: r["role"] for r in sorted_nodes if r.get("role")}
    if role_map:
        result["role_map"] = role_map

    # skill_map
    skill_map = {r["node_id"]: r["skill"] for r in sorted_nodes if r.get("skill")}
    if skill_map:
        result["skill_map"] = skill_map

    # adapter_map: per-state entries + optional default from flow_level_config
    per_state_adapters = {
        r["node_id"]: r["adapter"]
        for r in sorted_nodes
        if r.get("adapter") is not None
    }
    adapter_default = flow_level_config.get("adapter_default")
    if per_state_adapters or adapter_default is not None:
        adapter_map: dict = {}
        adapter_map.update(per_state_adapters)
        if adapter_default is not None:
            adapter_map["default"] = adapter_default
        if adapter_map:
            result["adapter_map"] = adapter_map

    # feedback_routing
    feedback_routing = flow_level_config.get("feedback_routing")
    if feedback_routing is not None:
        result["feedback_routing"] = feedback_routing

    # composition
    composition: dict = {}
    for r in sorted_nodes:
        cfg = json.loads(r["config_json"] or "{}")
        block = cfg.get("composition_block")
        if block is not None:
            composition[r["node_id"]] = block
    if composition:
        result["composition"] = composition

    # transition_rules
    transition_rules: dict = {}
    for r in sorted_nodes:
        cfg = json.loads(r["config_json"] or "{}")
        rule = cfg.get("transition_rule")
        if rule is not None:
            transition_rules[r["node_id"]] = rule
    if transition_rules:
        result["transition_rules"] = transition_rules

    # transition_actions
    transition_actions: dict = {}
    for edge in edge_rows:
        cfg = json.loads(edge["config_json"] or "{}")
        actions = cfg.get("actions")
        if actions is not None:
            key = f"{edge['source_node']}->{edge['target_node']}"
            transition_actions[key] = actions
    if transition_actions:
        result["transition_actions"] = transition_actions

    # scope_gate
    scope_gate = flow_level_config.get("scope_gate")
    if scope_gate is not None:
        result["scope_gate"] = scope_gate

    # gates
    gates: dict = {}
    for edge in edge_rows:
        cfg = json.loads(edge["config_json"] or "{}")
        edge_gates = cfg.get("gates")
        if edge_gates is not None:
            key = f"{edge['source_node']}->{edge['target_node']}"
            gates[key] = edge_gates
    if gates:
        result["gates"] = gates

    # _comments
    comments = flow_level_config.get("_comments")
    if comments is not None:
        result["_comments"] = comments

    return result


# ---------------------------------------------------------------------------
# DB-backed read helpers
# ---------------------------------------------------------------------------

def read_flow_nodes(conn: sqlite3.Connection, flow_def_id: int) -> list[dict]:
    """Return all node rows for a flow, ordered by position."""
    rows = conn.execute(
        "SELECT * FROM flow_nodes WHERE flow_def_id=? ORDER BY position ASC",
        (flow_def_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def read_flow_edges(conn: sqlite3.Connection, flow_def_id: int) -> list[dict]:
    """Return all edge rows for a flow, ordered by source_node, ordinal."""
    rows = conn.execute(
        "SELECT * FROM flow_edges WHERE flow_def_id=? ORDER BY source_node ASC, ordinal ASC",
        (flow_def_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def replace_flow_graph(
    conn: sqlite3.Connection,
    flow_def_id: int,
    flow_level_config: dict,
    node_rows: list[dict],
    edge_rows: list[dict],
    commit: bool = True,
) -> None:
    """Atomically replace all nodes+edges for a flow and update flow_definitions.config_json.
    Runs inside a single _get_write_lock + one commit (when commit=True).
    Pass commit=False when called from within an outer write lock (e.g. upsert_flow_definition).
    """
    with _get_write_lock(conn):
        conn.execute("DELETE FROM flow_nodes WHERE flow_def_id=?", (flow_def_id,))
        conn.execute("DELETE FROM flow_edges WHERE flow_def_id=?", (flow_def_id,))

        if node_rows:
            conn.executemany(
                "INSERT INTO flow_nodes "
                "(flow_def_id, node_id, node_type, agent, role, adapter, skill, is_terminal, position, config_json) "
                "VALUES (:flow_def_id, :node_id, :node_type, :agent, :role, :adapter, :skill, :is_terminal, :position, :config_json)",
                [{"flow_def_id": flow_def_id, **row} for row in node_rows],
            )

        if edge_rows:
            conn.executemany(
                "INSERT INTO flow_edges "
                "(flow_def_id, source_node, target_node, ordinal, config_json) "
                "VALUES (:flow_def_id, :source_node, :target_node, :ordinal, :config_json)",
                [{"flow_def_id": flow_def_id, **row} for row in edge_rows],
            )

        conn.execute(
            "UPDATE flow_definitions SET config_json=? WHERE id=?",
            (json.dumps(flow_level_config, ensure_ascii=False), flow_def_id),
        )

        if commit:
            conn.commit()


def _assemble_flow_dict(
    conn: sqlite3.Connection,
    flow_def_id: int,
    flow_level_config: dict,
) -> dict:
    """Reconstruct the YAML-equivalent dict from flow_nodes + flow_edges rows.
    Calls read_flow_nodes and read_flow_edges, then delegates to _assemble_from_parts.
    """
    nodes = read_flow_nodes(conn, flow_def_id)
    edges = read_flow_edges(conn, flow_def_id)
    return _assemble_from_parts(flow_level_config, nodes, edges)


# ---------------------------------------------------------------------------
# Core upsert / query functions
# ---------------------------------------------------------------------------

def upsert_flow_definition(
    conn: sqlite3.Connection,
    project_root,
    name: str,
    version: str,
    flow_yaml: str,
    file_path: str = "",
) -> int:
    """Upsert a flow definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO flow_definitions "
            "(project_root, name, version, flow_yaml, file_path, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_root,
                name,
                version,
                flow_yaml,
                file_path,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        flow_def_id = cur.lastrowid or 0
        conn.commit()

    # Decompose and store normalized rows — failure is non-fatal (blob is the fallback)
    try:
        flow_dict = yaml.safe_load(flow_yaml)
        if isinstance(flow_dict, dict):
            flow_level_cfg, nodes, edges = _decompose_flow_dict(flow_dict)
            replace_flow_graph(conn, flow_def_id, flow_level_cfg, nodes, edges, commit=True)
    except Exception:
        _log.warning("upsert_flow_definition: decomposition failed for '%s', blob stored as fallback", name)

    return flow_def_id


def read_flow_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return flow definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def read_flow_by_name(conn: sqlite3.Connection, name: str, project_root=None) -> dict | None:
    """Return a single flow definition by name, or None if not found."""
    if project_root is not None:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root=?",
            (name, project_root)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root IS NULL",
            (name,)
        ).fetchone()
        if row is None:
            # Fallback: any flow with this name
            row = conn.execute(
                "SELECT * FROM flow_definitions WHERE name=? ORDER BY project_root IS NULL DESC LIMIT 1",
                (name,)
            ).fetchone()
    return dict(row) if row else None


def _refresh_flows(conn: sqlite3.Connection) -> None:
    """Walk pathly_data/core/flows and upsert each .flow.yaml into flow_definitions.
    Called on every server start to keep DB in sync with filesystem.
    """
    from .catalog_items import _find_data_root
    data_root = _find_data_root()
    if data_root is None:
        return
    flows_dir = data_root / "core" / "flows"
    if not flows_dir.exists():
        return
    for f in sorted(flows_dir.glob("*.flow.yaml")):
        # team.flow.yaml -> team
        name = f.stem  # e.g. team.flow
        if name.endswith(".flow"):
            name = name[:-5]
        try:
            flow_yaml = f.read_text(encoding="utf-8")
            upsert_flow_definition(
                conn,
                project_root=None,
                name=name,
                version="",
                flow_yaml=flow_yaml,
                file_path=str(f).replace("\\", "/"),
            )
        except Exception:
            pass
