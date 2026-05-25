import { renderHook, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useFlowFile } from './useFlowFile'

const validYaml = `
version: 1
flow: test
states:
  - start
  - end
transitions:
  start:
    - end
  end: []
agent_map:
  start: planner
  end: reviewer
`.trim()

function mockRead(value: string | null) {
  ;(window.pathly.fs.read as ReturnType<typeof vi.fn>).mockResolvedValue(value)
}

function mockReadReject() {
  ;(window.pathly.fs.read as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('not found'))
}

describe('useFlowFile', () => {
  const markDirty = vi.fn()
  const clearDirty = vi.fn()
  const selectedItem = { path: '/project/flow.yaml' }

  beforeEach(() => {
    vi.clearAllMocks()
    mockRead(null)
  })

  it('loads valid YAML and sets flowData', async () => {
    mockRead(validYaml)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.flowData).not.toBeNull()
    expect(result.current.flowData?.flow).toBe('test')
    expect(result.current.yamlParseError).toBeNull()
  })

  it('silently clears state when readFile rejects', async () => {
    mockReadReject()
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.flowData).toBeNull()
    expect(result.current.rawYaml).toBe('')
  })

  it('sets yamlParseError containing "line" for malformed YAML', async () => {
    mockRead('key: [unterminated')
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.yamlParseError).not.toBeNull()
    expect(result.current.yamlParseError).toMatch(/line/i)
  })

  it('calls writeFile when handleYamlSave is invoked', async () => {
    mockRead(validYaml)
    const { result } = renderHook(() => useFlowFile(selectedItem, markDirty, clearDirty))

    await waitFor(() => expect(result.current.loading).toBe(false))

    await result.current.handleYamlSave('new content')

    expect(window.pathly.fs.write).toHaveBeenCalledWith('/project/flow.yaml', 'new content')
  })
})
