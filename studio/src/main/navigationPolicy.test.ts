import { describe, expect, it } from 'vitest'
import { navigationDecision, windowOpenDecision } from './navigationPolicy'

const DEV = 'http://localhost:5173/?PROJECT_PATH=%2Fp'
const PACKAGED = 'file:///Applications/Pathly.app/Contents/Resources/app.asar/out/renderer/index.html'

describe('navigationDecision', () => {
  it('keeps the app on its own origin', () => {
    expect(navigationDecision(DEV, 'http://localhost:5173/?board=x')).toBe('allow')
    expect(navigationDecision(PACKAGED, `${PACKAGED}?terminal=t1`)).toBe('allow')
  })

  it('sends web links to the system browser instead of loading them in-window', () => {
    expect(navigationDecision(DEV, 'https://evil.example/x')).toBe('external')
    expect(navigationDecision(DEV, 'http://localhost:9999/')).toBe('external')
    expect(navigationDecision(PACKAGED, 'https://example.com')).toBe('external')
    expect(navigationDecision(DEV, 'mailto:a@b.c')).toBe('external')
  })

  it('drops script, data and file navigations from a web origin', () => {
    expect(navigationDecision(DEV, 'javascript:alert(1)')).toBe('block')
    expect(navigationDecision(DEV, 'data:text/html,<b>x</b>')).toBe('block')
    expect(navigationDecision(DEV, 'file:///etc/passwd')).toBe('block')
    expect(navigationDecision(DEV, 'not a url')).toBe('block')
  })
})

describe('windowOpenDecision', () => {
  it('never opens an app window; web links go to the browser', () => {
    expect(windowOpenDecision('https://example.com')).toBe('external')
    expect(windowOpenDecision('http://localhost:5173/')).toBe('external')
    expect(windowOpenDecision('javascript:alert(1)')).toBe('block')
    expect(windowOpenDecision('file:///etc/passwd')).toBe('block')
  })
})
