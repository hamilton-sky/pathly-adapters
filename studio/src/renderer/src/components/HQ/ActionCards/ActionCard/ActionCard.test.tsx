import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ActionCard } from './ActionCard'
import type { HqActionCard } from '../../../../store/chatStore'

const CARD: HqActionCard = {
  id: 'c1', name: 'stop_run', label: 'Stop a run', risk: ['changes state', 'hard to undo'], runs_on: 'server',
  args: { run_id: 'r1' }, title: 'Stop run r1 (team · BUILDING)', status: 'proposed', fingerprint: 'running',
  board: 'b', projectRoot: null,
}

describe('ActionCard', () => {
  it('shows verb + target and its risk; Run is not auto-focused', () => {
    render(<ActionCard card={CARD} runnable onRun={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('group', { name: /Stop run r1/ })).toBeTruthy()
    expect(screen.getByText('changes state · hard to undo')).toBeTruthy()
    expect(document.activeElement).not.toBe(screen.getByRole('button', { name: 'Run' }))
  })

  it('Run waits for the card above: aria-disabled with the reason, click ignored', () => {
    const onRun = vi.fn()
    render(<ActionCard card={CARD} runnable={false} onRun={onRun} onCancel={vi.fn()} />)
    const run = screen.getByRole('button', { name: 'Run' })
    expect(run.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(run.getAttribute('aria-describedby') ?? '')?.textContent).toMatch(/action above/)
    fireEvent.click(run)
    expect(onRun).not.toHaveBeenCalled()
  })

  it('Run and Cancel call through', () => {
    const onRun = vi.fn()
    const onCancel = vi.fn()
    render(<ActionCard card={CARD} runnable onRun={onRun} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Run' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect([onRun.mock.calls.length, onCancel.mock.calls.length]).toEqual([1, 1])
  })

  it('a settled card is a one-line record, without buttons', () => {
    render(<ActionCard card={{ ...CARD, status: 'stale', summary: 'Not run: the board changed' }} runnable onRun={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('Not run: the board changed')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
