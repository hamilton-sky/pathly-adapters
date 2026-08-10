import { renderHook, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { useRunDetail } from './useRunDetail'
import type { RunDetail } from '../types'

vi.mock('../../../lib/config', () => ({
  apiFetch: vi.fn(),
  PATHLY_API_BASE: 'http://127.0.0.1:8765',
}))

import { apiFetch } from '../../../lib/config'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
  close(): void {
    this.closed = true
  }
}

function mockRunDetail(): RunDetail {
  return {
    run: {
      run_id: 'run-1',
      project_root: '/p',
      feature: 'f',
      board_scope: null,
      status: 'running',
      adapter: 'claude',
      kind: 'single',
      started_at: null,
      finished_at: null,
      stage_count: null,
      cost_usd: 0,
      tokens_total: 0,
    },
    stages: [],
    logs: [],
    board: [],
    artifacts: [],
    cost: { cost_usd: 0, tokens_total: 0, invocations: 0 },
  }
}

const apiFetchMock = apiFetch as unknown as ReturnType<typeof vi.fn>

describe('useRunDetail live feed (SSE)', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    apiFetchMock.mockReset()
    apiFetchMock.mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => mockRunDetail(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens an EventSource for GET /events/runs?run_id=<id>', async () => {
    const { result } = renderHook(() => useRunDetail('run-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe(
      'http://127.0.0.1:8765/events/runs?run_id=run-1',
    )
  })

  it('ignores the initial "connected" event but refreshes on a real run event', async () => {
    const { result } = renderHook(() => useRunDetail('run-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    const callsAfterInitialLoad = apiFetchMock.mock.calls.length
    const es = FakeEventSource.instances[0]

    act(() => {
      es.onmessage?.({ data: JSON.stringify({ type: 'connected' }) } as MessageEvent)
    })
    expect(apiFetchMock.mock.calls.length).toBe(callsAfterInitialLoad)

    act(() => {
      es.onmessage?.(
        { data: JSON.stringify({ type: 'RUNNER_STATUS', run_id: 'run-1' }) } as MessageEvent,
      )
    })
    await waitFor(() =>
      expect(apiFetchMock.mock.calls.length).toBe(callsAfterInitialLoad + 1),
    )
  })

  it('closes the EventSource on unmount', async () => {
    const { result, unmount } = renderHook(() => useRunDetail('run-1'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    const es = FakeEventSource.instances[0]
    expect(es.closed).toBe(false)
    unmount()
    expect(es.closed).toBe(true)
  })
})
