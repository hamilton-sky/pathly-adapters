import { renderHook, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useFlowFile } from './useFlowFile'

vi.mock('../../../services/pathlyApi', () => ({
  fetchFlowGraph: vi.fn(),
  saveFlow: vi.fn().mockResolvedValue(undefined),
  saveFlowGraph: vi.fn().mockResolvedValue(undefined),
}))

import * as pathlyApi from '../../../services/pathlyApi'

const validGraph = {
  version: 1,
  flow: 'test',
  states: ['start', 'end'],
  transitions: { start: ['end'], end: [] },
  agent_map: { start: 'planner', end: 'reviewer' },
}

function mockFetchGraph(graph: typeof validGraph | null) {
  ;(pathlyApi.fetchFlowGraph as ReturnType<typeof vi.fn>).mockResolvedValue(
    graph ? { name: 'test', graph } : null
  )
}

function mockFetchGraphReject() {
  ;(pathlyApi.fetchFlowGraph as ReturnType<typeof vi.fn>).mockRejectedValue(
    new Error('network error')
  )
}

describe('useFlowFile', () => {
  const markDirty = vi.fn()
  const clearDirty = vi.fn()
  const selectedItem = { path: '/project/test.flow.yaml' }

  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchGraph(null)
  })

  it('loads flow graph and sets flowData', async () => {
    mockFetchGraph(validGraph)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.flowData).not.toBeNull()
    expect(result.current.flowData?.flow).toBe('test')
    expect(result.current.yamlParseError).toBeNull()
  })

  it('sets yamlParseError when graph is null', async () => {
    mockFetchGraph(null)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.flowData).toBeNull()
    expect(result.current.yamlParseError).not.toBeNull()
  })

  it('silently clears state when fetchFlowGraph rejects', async () => {
    mockFetchGraphReject()
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.flowData).toBeNull()
    expect(result.current.rawYaml).toBe('')
  })

  it('calls saveFlowGraph when handleVisualSave is invoked', async () => {
    mockFetchGraph(validGraph)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await result.current.handleVisualSave()

    expect(pathlyApi.saveFlowGraph).toHaveBeenCalledWith('test', validGraph)
  })

  it('calls saveFlow when handleYamlSave is invoked (YAML tab path unchanged)', async () => {
    mockFetchGraph(validGraph)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await result.current.handleYamlSave('new yaml content')

    expect(pathlyApi.saveFlow).toHaveBeenCalledWith('test', 'new yaml content')
  })
})
