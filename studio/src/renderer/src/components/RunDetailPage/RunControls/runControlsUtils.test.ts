import { describe, expect, it } from 'vitest'
import { visibleFlowActions } from './runControlsUtils'

describe('visibleFlowActions', () => {
  it('shows pause + reroute while running', () => {
    expect(visibleFlowActions('running')).toEqual(['pause', 'reroute'])
  })

  it('shows resume + advance + reroute while paused', () => {
    expect(visibleFlowActions('paused')).toEqual(['resume', 'advance', 'reroute'])
  })

  it('shows only reroute while awaiting a human decision', () => {
    expect(visibleFlowActions('awaiting_decision')).toEqual(['reroute'])
  })

  it('shows retry once the run has finished (done/aborted/error)', () => {
    expect(visibleFlowActions('done')).toEqual(['retry'])
    expect(visibleFlowActions('aborted')).toEqual(['retry'])
    expect(visibleFlowActions('error')).toEqual(['retry'])
  })
})
