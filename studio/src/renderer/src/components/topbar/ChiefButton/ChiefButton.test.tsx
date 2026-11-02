import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ChiefNotice } from '../../../services/chiefApi'
import * as api from '../../../services/chiefApi'
import { useProjectStore } from '../../../store/projectStore'
import { ChiefButton } from './ChiefButton'

vi.mock('../../../services/chiefApi', () => ({
  getChiefNotices: vi.fn(),
  markChiefNoticesRead: vi.fn(),
  fetchChiefPresets: vi.fn(),
  fetchChiefSession: vi.fn(),
  openChief: vi.fn(),
  closeChief: vi.fn(),
}))

const ROOT = '/work/proj'

function notice(over: Partial<ChiefNotice>): ChiefNotice {
  return {
    run_id: 'run-a',
    session_run_id: 'chief-1',
    started_at: 1,
    kind: 'flow',
    status: 'done',
    outcome: 'success',
    error: null,
    cost_usd: 0.5,
    finished_at: 2,
    open_questions: 0,
    ...over,
  }
}

beforeEach(() => {
  vi.mocked(api.getChiefNotices).mockReset()
  vi.mocked(api.markChiefNoticesRead).mockReset().mockResolvedValue(2)
  vi.mocked(api.fetchChiefPresets).mockResolvedValue(null)
  vi.mocked(api.fetchChiefSession).mockResolvedValue({ open: false })
  act(() => useProjectStore.getState().setProjectPath(ROOT))
})

afterEach(() => {
  act(() => useProjectStore.getState().setProjectPath(''))
})

describe('ChiefButton notices', () => {
  it('shows the unread count as a badge when a chief run has ended', async () => {
    vi.mocked(api.getChiefNotices).mockResolvedValue([
      notice({ run_id: 'run-a' }),
      notice({ run_id: 'run-b', status: 'error' }),
    ])
    render(<ChiefButton compact={false} />)
    const badge = await screen.findByTestId('topbar-chief-badge')
    expect(badge.textContent).toBe('2')
    expect(api.getChiefNotices).toHaveBeenCalledWith(ROOT)
  })

  it('shows no badge when nothing is unread', async () => {
    vi.mocked(api.getChiefNotices).mockResolvedValue([])
    render(<ChiefButton compact={false} />)
    await waitFor(() => expect(api.getChiefNotices).toHaveBeenCalledWith(ROOT))
    expect(screen.queryByTestId('topbar-chief-badge')).toBeNull()
  })

  it('opening the menu lists the notices and marks the listed runs read', async () => {
    vi.mocked(api.getChiefNotices).mockResolvedValue([
      notice({ run_id: 'run-a', open_questions: 2 }),
      notice({ run_id: 'run-b', status: 'error', outcome: 'failed', error: 'tests failed', cost_usd: 1.25 }),
    ])
    render(<ChiefButton compact={false} />)
    await screen.findByTestId('topbar-chief-badge')

    fireEvent.click(screen.getByTestId('topbar-chief'))

    const list = await screen.findByRole('list', { name: 'Finished chief runs' })
    expect(list.textContent).toContain('run-a')
    expect(list.textContent).toContain('2 questions waiting')
    expect(list.textContent).toContain('run-b')
    expect(list.textContent).toContain('error')
    expect(list.textContent).toContain('tests failed')
    expect(list.textContent).toContain('$1.25')
    await waitFor(() =>
      expect(api.markChiefNoticesRead).toHaveBeenCalledWith(ROOT, ['run-a', 'run-b']),
    )
    await waitFor(() => expect(screen.queryByTestId('topbar-chief-badge')).toBeNull())
  })
})
