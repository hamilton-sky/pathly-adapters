"""Flow graph decomposition, assembly, and DB-backed node/edge helpers.

Pure operations: decompose a YAML flow dict into node/edge rows, assemble
node/edge rows back into a YAML-equivalent dict, and read/replace those rows
in the DB. The lifecycle functions (upsert, read-by-name) live in flow_defs.py.
"""

from __future__ import annotations

import json
import sqlite3

from ..connection import _get_write_lock

# Adapter used to satisfy the FSM validator's "adapter_map: 'default' key is
# required" rule when a flow declares per-state adapters but no default. Kept in
# sync with fsm/state.py `_KNOWN_ADAPTERS` and the studio serializer's DEFAULT_ADAPTER.
_DEFAULT_ADAPTER = "claude"

# Top-level flow keys that are decomposed into node/edge rows — everything ELSE is
# carried verbatim as flow-level config so new/custom keys round-trip losslessly.
_STRUCTURAL_FLOW_KEYS = frozenset(
    {
        "states",
        "transitions",
        "agent_map",
        "role_map",
        "skill_map",
        "adapter_map",
        "transition_rules",
        "composition",
        "transition_actions",
        "gates",
    }
)

# Flow-level keys explicitly reconstructed by _assemble_from_parts; the pass-through
# at the end restores any OTHER flow_level_config key (escalation_routing, custom keys).
_ASSEMBLED_FLOW_KEYS = frozenset(
    {
        "version",
        "flow",
        "storage_path",
        "feedback_routing",
        "feedback_priority",
        "scope_gate",
        "_comments",
        "adapter_default",
    }
)


def ensure_adapter_map_default(flow_dict: dict) -> dict:
    """Normalize ``flow_dict['adapter_map']`` so a serialized flow always passes the
    FSM validator (``fsm/state.py``): a *non-empty* adapter_map MUST carry a
    ``default`` key. Mutates and returns ``flow_dict`` in place.

    - absent / non-dict adapter_map → left untouched (adapter_map is optional)
    - empty ``{}`` → dropped (an empty map has no default and is invalid)
    - per-state entries but no ``default`` → inject ``default='claude'`` FIRST
      (readable, canonical ordering — matches the on-disk shape)

    Mirrors ``normalizeAdapterMap`` in
    ``studio/src/renderer/src/components/FlowEditor/utils/serializeFlow.ts``.
    """
    am = flow_dict.get("adapter_map")
    if not isinstance(am, dict):
        return flow_dict
    if not am:
        flow_dict.pop("adapter_map", None)
    elif "default" not in am:
        flow_dict["adapter_map"] = {"default": _DEFAULT_ADAPTER, **am}
    return flow_dict


def _decompose_flow_dict(flow_dict: dict) -> tuple[dict, list[dict], list[dict]]:
    """Split a parsed YAML flow dict into (flow_level_config, node_rows, edge_rows).

    Returns:
        flow_level_config — dict with keys: version, flow, storage_path,
                            feedback_routing, scope_gate, adapter_default, _comments
        node_rows         — list of dicts with keys: node_id, node_type, agent, role,
                            adapter, skill, is_terminal, position, config_json
        edge_rows         — list of dicts with keys: source_node, target_node,
                            ordinal, config_json
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
    for key, val in flow_dict.items():
        if key in _STRUCTURAL_FLOW_KEYS or val is None:
            continue
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

        node_rows.append(
            {
                "node_id": state,
                "node_type": "state",
                "position": position,
                "agent": agent_map.get(state),
                "role": role_map.get(state),
                "adapter": per_state_adapter,
                "skill": skill_map.get(state),
                "is_terminal": is_terminal,
                "config_json": (
                    json.dumps(node_cfg, ensure_ascii=False) if node_cfg else None
                ),
            }
        )

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
            edge_rows.append(
                {
                    "source_node": state,
                    "target_node": target,
                    "ordinal": ordinal,
                    "config_json": (
                        json.dumps(edge_cfg, ensure_ascii=False) if edge_cfg else None
                    ),
                }
            )

    return flow_level_config, node_rows, edge_rows


def _assemble_from_parts(
    flow_level_config: dict,
    node_rows: list[dict],
    edge_rows: list[dict],
) -> dict:
    """Pure inverse of _decompose_flow_dict. Used by round-trip tests and _assemble_flow_dict."""
    result: dict = {}

    for key in ("version", "flow", "storage_path"):
        if key in flow_level_config:
            result[key] = flow_level_config[key]

    sorted_nodes = sorted(node_rows, key=lambda r: r["position"])
    result["states"] = [r["node_id"] for r in sorted_nodes]

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

    agent_map = {r["node_id"]: r["agent"] for r in sorted_nodes if r.get("agent")}
    if agent_map:
        result["agent_map"] = agent_map

    role_map = {r["node_id"]: r["role"] for r in sorted_nodes if r.get("role")}
    if role_map:
        result["role_map"] = role_map

    skill_map = {r["node_id"]: r["skill"] for r in sorted_nodes if r.get("skill")}
    if skill_map:
        result["skill_map"] = skill_map

    per_state_adapters = {
        r["node_id"]: r["adapter"] for r in sorted_nodes if r.get("adapter") is not None
    }
    adapter_default = flow_level_config.get("adapter_default")
    if per_state_adapters or adapter_default is not None:
        # The FSM validator requires a 'default' whenever adapter_map is present, so
        # synthesize one when per-state adapters exist without it — otherwise a graph
        # round-trip could emit an invalid flow. `default` goes first for readability.
        if adapter_default is None:
            adapter_default = _DEFAULT_ADAPTER
        result["adapter_map"] = {"default": adapter_default, **per_state_adapters}

    feedback_routing = flow_level_config.get("feedback_routing")
    if feedback_routing is not None:
        result["feedback_routing"] = feedback_routing

    # Smart fix-routing (DESIGN.md ss1.5) — an optional flow-level priority list, same
    # shape/lifecycle as feedback_routing above: a plain list, not decomposed into
    # nodes/edges, so it round-trips explicitly rather than through the structural tables.
    feedback_priority = flow_level_config.get("feedback_priority")
    if feedback_priority is not None:
        result["feedback_priority"] = feedback_priority

    composition: dict = {}
    for r in sorted_nodes:
        cfg = json.loads(r["config_json"] or "{}")
        block = cfg.get("composition_block")
        if block is not None:
            composition[r["node_id"]] = block
    if composition:
        result["composition"] = composition

    transition_rules: dict = {}
    for r in sorted_nodes:
        cfg = json.loads(r["config_json"] or "{}")
        rule = cfg.get("transition_rule")
        if rule is not None:
            transition_rules[r["node_id"]] = rule
    if transition_rules:
        result["transition_rules"] = transition_rules

    transition_actions: dict = {}
    for edge in edge_rows:
        cfg = json.loads(edge["config_json"] or "{}")
        actions = cfg.get("actions")
        if actions is not None:
            key = f"{edge['source_node']}->{edge['target_node']}"
            transition_actions[key] = actions
    if transition_actions:
        result["transition_actions"] = transition_actions

    scope_gate = flow_level_config.get("scope_gate")
    if scope_gate is not None:
        result["scope_gate"] = scope_gate

    gates: dict = {}
    for edge in edge_rows:
        cfg = json.loads(edge["config_json"] or "{}")
        edge_gates = cfg.get("gates")
        if edge_gates is not None:
            key = f"{edge['source_node']}->{edge['target_node']}"
            gates[key] = edge_gates
    if gates:
        result["gates"] = gates

    comments = flow_level_config.get("_comments")
    if comments is not None:
        result["_comments"] = comments

    for key, val in flow_level_config.items():
        if key in _ASSEMBLED_FLOW_KEYS or key in result:
            continue
        result[key] = val

    return result


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
    """Atomically replace all nodes+edges for a flow and update flow_definitions.config_json."""
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
    """Reconstruct the YAML-equivalent dict from flow_nodes + flow_edges rows."""
    nodes = read_flow_nodes(conn, flow_def_id)
    edges = read_flow_edges(conn, flow_def_id)
    return _assemble_from_parts(flow_level_config, nodes, edges)
