import { describe, it, expect } from 'vitest'
import * as jsYaml from 'js-yaml'
import { normalizeAdapterMap, normalizeFlow, serializeFlow } from './serializeFlow'
import type { FlowYaml } from '../../../types'

const base: FlowYaml = {
  version: 1,
  flow: 'consult',
  states: ['PO_DISCUSSING', 'ARCHITECTING', 'PLANNING'],
  transitions: {
    PO_DISCUSSING: ['ARCHITECTING'],
    ARCHITECTING: ['PLANNING'],
    PLANNING: [],
  },
  agent_map: {},
}

describe('normalizeAdapterMap', () => {
  it('returns undefined for absent or empty maps', () => {
    expect(normalizeAdapterMap(undefined)).toBeUndefined()
    expect(normalizeAdapterMap({})).toBeUndefined()
  })

  it('injects default=claude FIRST when per-stage adapters have no default', () => {
    const out = normalizeAdapterMap({ PO_DISCUSSING: 'codex', ARCHITECTING: 'claude' })
    expect(out).toEqual({ default: 'claude', PO_DISCUSSING: 'codex', ARCHITECTING: 'claude' })
    expect(Object.keys(out!)[0]).toBe('default')
  })

  it('leaves a map with an explicit default unchanged (same reference)', () => {
    const input = { default: 'codex', PO_DISCUSSING: 'codex' }
    expect(normalizeAdapterMap(input)).toBe(input)
  })
})

describe('serializeFlow', () => {
  it('emits adapter_map.default so the output satisfies the FSM validator rule', () => {
    const flow: FlowYaml = { ...base, adapter_map: { PO_DISCUSSING: 'codex', ARCHITECTING: 'claude' } }
    const parsed = jsYaml.load(serializeFlow(flow)) as FlowYaml
    const adapterMap = parsed.adapter_map as Record<string, string>
    // Mirrors the FSM validator's hard requirement (src/pathly_orchestrator/fsm/state.py).
    expect(adapterMap).toBeDefined()
    expect('default' in adapterMap).toBe(true)
    expect(adapterMap.default).toBe('claude')
    expect(adapterMap.PO_DISCUSSING).toBe('codex')
  })

  it('drops an empty adapter_map instead of emitting an invalid `adapter_map: {}`', () => {
    const flow: FlowYaml = { ...base, adapter_map: {} }
    const parsed = jsYaml.load(serializeFlow(flow)) as FlowYaml
    expect(parsed.adapter_map).toBeUndefined()
  })

  it('omits adapter_map entirely when the flow has none', () => {
    const parsed = jsYaml.load(serializeFlow(base)) as FlowYaml
    expect(parsed.adapter_map).toBeUndefined()
  })
})

describe('normalizeFlow', () => {
  it('returns the same reference when nothing changes', () => {
    const flow: FlowYaml = { ...base, adapter_map: { default: 'claude', PO_DISCUSSING: 'codex' } }
    expect(normalizeFlow(flow)).toBe(flow)
  })

  it('returns the same reference when there is no adapter_map', () => {
    expect(normalizeFlow(base)).toBe(base)
  })

  it('drops an empty adapter_map from the object', () => {
    const flow: FlowYaml = { ...base, adapter_map: {} }
    const out = normalizeFlow(flow)
    expect(out).not.toBe(flow)
    expect('adapter_map' in out).toBe(false)
  })
})
