import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import MarkdownRenderer from './MarkdownRenderer'

// Regression: this renderer shows board posts, artifacts and agent text, and once
// injected raw marked() output — <img onerror> ran and javascript: links were live.
describe('MarkdownRenderer', () => {
  it('escapes raw HTML instead of injecting it', () => {
    const { container } = render(
      <MarkdownRenderer content={'Hi <img src=x onerror="alert(1)"> and <script>alert(2)</script>'} />,
    )
    expect(container.querySelector('img, script')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">')
  })

  it('drops javascript: hrefs and keeps the label', () => {
    const { container } = render(<MarkdownRenderer content={'[click](javascript:alert(1))'} />)
    expect(container.querySelector('a')).toBeNull()
    expect(container.textContent).toContain('click')
  })

  it('keeps web links, opening outside the app', () => {
    const { container } = render(<MarkdownRenderer content={'[docs](https://example.com)'} />)
    const a = container.querySelector('a')
    expect(a?.getAttribute('href')).toBe('https://example.com')
    expect(a?.getAttribute('rel')).toBe('noopener noreferrer')
  })

  it('shows images only when the caller opts in', () => {
    const md = '![diagram](https://example.com/d.png)'
    expect(render(<MarkdownRenderer content={md} />).container.querySelector('img')).toBeNull()
    const img = render(<MarkdownRenderer content={md} images />).container.querySelector('img')
    expect(img?.getAttribute('src')).toBe('https://example.com/d.png')
    expect(img?.getAttribute('alt')).toBe('diagram')
  })
})
