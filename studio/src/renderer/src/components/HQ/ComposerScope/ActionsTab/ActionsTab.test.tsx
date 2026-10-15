import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ActionsTab } from './ActionsTab'
import type { HqActionCatalog, HqCatalogAction } from '../../../../services/hqActionsApi'

const action = (name: string, domain = 'runs'): HqCatalogAction => ({
  name, domain, label: name, risk: ['changes state'], description: '', runs_on: 'server',
  available: true, default_available: true, schema_tokens: 70,
})
const NAMES = ['a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9']
const CATALOG: HqActionCatalog = {
  max_enabled: 8,
  domains: [{ id: 'runs', label: 'Runs' }],
  presets: [{ id: 'p', label: 'Run control', actions: ['a1', 'a2'] }],
  actions: NAMES.map((n) => action(n)),
}

function sel(ticked: string[], over: Record<string, unknown> = {}) {
  return {
    catalog: CATALOG,
    available: CATALOG.actions,
    ticked,
    enabledCount: ticked.length,
    atCap: ticked.length >= 8,
    schemaTokens: 0,
    builtIn: true,
    toggle: vi.fn(),
    applyPreset: vi.fn(),
    clear: vi.fn(),
    ...over,
  }
}

describe('ActionsTab', () => {
  it('at the cap an unticked row is aria-disabled with the reason, never auto-unticking', () => {
    const s = sel(NAMES.slice(0, 8))
    render(<ActionsTab sel={s} />)
    const blocked = screen.getByRole('checkbox', { name: /a9/ })
    expect(blocked.getAttribute('aria-disabled')).toBe('true')
    expect(blocked.hasAttribute('disabled')).toBe(false) // still focusable
    const reason = document.getElementById(blocked.getAttribute('aria-describedby') ?? '')
    expect(reason?.textContent).toMatch(/At the limit/)
    fireEvent.click(blocked)
    expect(s.toggle).not.toHaveBeenCalled()
    expect(screen.getByRole('status').textContent).toBe('8 of 8 enabled')
  })

  it('ticks below the cap and applies a preset', () => {
    const s = sel(['a1'])
    render(<ActionsTab sel={s} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /a2/ }))
    expect(s.toggle).toHaveBeenCalledWith('a2')
    fireEvent.click(screen.getByRole('button', { name: '+ Run control' }))
    expect(s.applyPreset).toHaveBeenCalledWith(['a1', 'a2'])
  })

  it('says why actions do nothing on Ollama, and where to turn them on', () => {
    const { rerender } = render(<ActionsTab sel={sel([], { builtIn: false })} />)
    expect(screen.getByRole('note').textContent).toMatch(/built-in model/)
    rerender(<ActionsTab sel={sel([], { available: [] })} />)
    expect(screen.getByText(/Settings → Intelligence → HQ actions/)).toBeTruthy()
  })
})
