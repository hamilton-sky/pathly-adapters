import { afterEach, describe, expect, it } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { ComposerScope } from './ComposerScope'
import { useHqComposerStore } from '../../../store/hqComposerStore'
import { useHqContextStore } from '../../../store/hqContextStore'

afterEach(() => {
  act(() => {
    useHqComposerStore.getState().closeScope()
    useHqContextStore.getState().reset()
  })
})

describe('ComposerScope', () => {
  it('shows the Context chip with the ticked count, popover closed', () => {
    render(<ComposerScope />)
    const chip = screen.getByRole('button', { name: 'Context: 5 of 6 board sections' })
    expect(chip.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens the popover from the chip and saves a ticked section', () => {
    render(<ComposerScope />)
    fireEvent.click(screen.getByRole('button', { name: /^Context:/ }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    fireEvent.click(screen.getByRole('checkbox', { name: /Artifact summaries/ }))
    expect(useHqContextStore.getState().enabled.summaries).toBe(true)
    expect(screen.getByRole('button', { name: 'Context: 6 of 6 board sections' })).toBeTruthy()
  })

  it('Escape closes the popover and returns focus to its chip', () => {
    render(<ComposerScope />)
    const chip = screen.getByRole('button', { name: /^Context:/ })
    fireEvent.click(chip)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(chip)
  })

  it('a click outside closes it', () => {
    render(<div><ComposerScope /><p>elsewhere</p></div>)
    fireEvent.click(screen.getByRole('button', { name: /^Context:/ }))
    fireEvent.mouseDown(screen.getByText('elsewhere'))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens when another surface asks (an answer\'s "Adjust for next question")', () => {
    render(<ComposerScope />)
    act(() => useHqComposerStore.getState().openScope('context'))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getAllByRole('checkbox')).toHaveLength(6)
  })
})
