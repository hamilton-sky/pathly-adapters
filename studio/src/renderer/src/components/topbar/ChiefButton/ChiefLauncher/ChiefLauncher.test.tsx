import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import * as api from '../../../../services/chiefApi'
import { ChiefLauncher } from './ChiefLauncher'

vi.mock('../../../../services/chiefApi', () => ({
  getChiefNotices: vi.fn(),
  markChiefNoticesRead: vi.fn(),
  fetchChiefPresets: vi.fn(),
  fetchChiefSession: vi.fn(),
  openChief: vi.fn(),
  closeChief: vi.fn(),
}))

const CODEX_NOTE = /a codex chief can read files outside the project/i
const SAME_USER_NOTE = /another program running as you can still read/i

beforeEach(() => {
  localStorage.clear()
  vi.mocked(api.fetchChiefPresets).mockResolvedValue({
    presets: [
      {
        name: 'status',
        label: 'Status',
        tier: 'status',
        text: 'You are the chief.\n',
        source: 'builtin',
        scope: null,
      },
    ],
    tiers: { status: [], planner: [], operator: [] },
    limits: { max_runs_per_session: 5, max_cost_usd_per_run: 2 },
  })
  vi.mocked(api.fetchChiefSession).mockResolvedValue({ open: false })
})

describe('ChiefLauncher codex note', () => {
  it('says what a codex chief cannot promise once codex is picked', async () => {
    render(<ChiefLauncher projectRoot="/work/proj" onOpened={() => undefined} />)
    fireEvent.click(await screen.findByRole('button', { name: /^AI engine:/ }))
    expect(screen.queryByText(CODEX_NOTE)).toBeNull()

    fireEvent.click(screen.getByRole('menuitemradio', { name: /^Codex/ }))

    expect(screen.getByText(CODEX_NOTE).textContent).toMatch(/not safe to leave alone yet/i)
  })
})

describe('ChiefLauncher same-user note', () => {
  it('tells a claude chief that a program running as the person can read its environment', async () => {
    render(<ChiefLauncher projectRoot="/work/proj" onOpened={() => undefined} />)
    const line = await screen.findByText(SAME_USER_NOTE)
    expect(line.textContent).toMatch(/keep untrusted programs off this account/i)
    expect(screen.queryByText(CODEX_NOTE)).toBeNull()
  })

  it('shows CODEX_NOTE, not the same-user line, for a codex chief', async () => {
    render(<ChiefLauncher projectRoot="/work/proj" onOpened={() => undefined} />)
    await screen.findByText(SAME_USER_NOTE)
    fireEvent.click(screen.getByRole('button', { name: /^AI engine:/ }))
    fireEvent.click(screen.getByRole('menuitemradio', { name: /^Codex/ }))

    expect(screen.getByText(CODEX_NOTE)).toBeTruthy()
    expect(screen.queryByText(SAME_USER_NOTE)).toBeNull()
  })
})
