import * as jsYaml from 'js-yaml'
import type { FlowYaml } from '../../../types'

/**
 * Adapter injected as `adapter_map.default` when a flow declares per-state adapters
 * but no default. Mirrors `_DEFAULT_ADAPTER` in
 * `src/pathly_orchestrator/db/queries/flow_graph_ops.py`.
 */
export const DEFAULT_ADAPTER = 'claude'

/**
 * Normalize an `adapter_map` so a serialized flow always passes the FSM validator
 * (`src/pathly_orchestrator/fsm/state.py`), which requires a `default` key whenever
 * `adapter_map` is present:
 *   - absent / empty → `undefined` (the key is optional — drop it entirely)
 *   - has `default`  → returned unchanged
 *   - per-state only → `{ default: 'claude', ...map }` (default first, for readable output)
 *
 * Mirrors `ensure_adapter_map_default` in `flow_graph_ops.py`.
 */
export function normalizeAdapterMap(
  adapterMap: Record<string, string> | undefined
): Record<string, string> | undefined {
  if (!adapterMap || Object.keys(adapterMap).length === 0) return undefined
  if ('default' in adapterMap) return adapterMap
  return { default: DEFAULT_ADAPTER, ...adapterMap }
}

/**
 * Return `flow` with a normalized `adapter_map`, or the same reference when nothing
 * changed. An empty `adapter_map` is dropped from the object entirely.
 */
export function normalizeFlow(flow: FlowYaml): FlowYaml {
  const normalized = normalizeAdapterMap(flow.adapter_map)
  if (normalized === flow.adapter_map) return flow
  const next = { ...flow }
  if (normalized) next.adapter_map = normalized
  else delete next.adapter_map
  return next
}

/**
 * Canonical `FlowYaml` → YAML serializer for the flow editor. Guarantees the emitted
 * document is a valid flow file (a non-empty `adapter_map` always carries `default`)
 * before dumping with a stable key order.
 */
export function serializeFlow(flow: FlowYaml): string {
  return jsYaml.dump(normalizeFlow(flow), { lineWidth: 120 })
}
